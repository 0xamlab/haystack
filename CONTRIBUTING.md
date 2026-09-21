# Contributing to Algenta

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
git clone https://github.com/thyn-ai/algenta
cd algenta
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

## Contributions and licensing

There is no Contributor License Agreement. Contributions are inbound = outbound:
by submitting a pull request you license your contribution to Seville AI Technologies, Inc. d/b/a Thyn (thyn.ai)
under the [Algenta Community License](./LICENSE) that covers this repository, consistent
with GitHub Terms of Service §D.6.

---

## Code style

**Python:** [ruff](https://docs.astral.sh/ruff/) is the only linter *and* formatter (no
black, no isort). It is pinned to `ruff==0.12.0` in `mojo_env/pixi.toml`; configuration lives
in `pyproject.toml` (`[tool.ruff]`, `[tool.mypy]`).

```bash
make format      # ruff check --fix . && ruff format .
make lint        # ruff check . && ruff format --check . && mypy <the four packages>
make typecheck   # mypy apps/api_server apps/mcp_server apps/runtime apps/worker
```

`make typecheck` is currently red over that scope; new code should not add to the count.

**TypeScript:**
```bash
pnpm lint        # == make js-lint: packages/ts-sdk + apps/gateway
```

**Pre-commit hooks** (`.pre-commit-config.yaml`; needs pre-commit >= 3.2.0 and a `python3.14`
on PATH, the same interpreter series `mojo_env/pixi.toml` pins):

```bash
pip install pre-commit      # or: uv tool install pre-commit
pre-commit install          # installs BOTH stages (default_install_hook_types)
```

- On **commit**: whitespace/EOF fixers, YAML/JSON/TOML syntax (`check-yaml` skips the
  Go-templated `infra/helm/`), merge-conflict markers, files > 500 KB, no direct commits to
  `main`, then `ruff --fix` and `ruff-format` on the staged Python files.
- On **push**: nothing yet. The `mypy` hook covers exactly the four `make typecheck` packages
  but is `stages: [manual]` until `make typecheck` is green; run it with
  `pre-commit run mypy --all-files --hook-stage manual`.

`tests/test_precommit_pins.py` (in `pnpm test:hardening`) keeps the ruff hook `rev` equal to
the pixi pin, the mypy hook scope equal to the Makefile, and the mypy hook's
`pydantic`/`types-redis` versions equal to pixi -- bump them together.

All CI checks must pass.

---

## Reporting issues

- **Security vulnerabilities** → security@algenta.ai (do NOT open public issues)
- **Bugs** → [GitHub Issues](https://github.com/thyn-ai/algenta/issues) with the `bug` label
- **Feature requests** → [GitHub Discussions](https://github.com/thyn-ai/algenta/discussions)
- **Questions** → [Discord](https://algenta.ai/discord)

---

## Community

- Discord: https://algenta.ai/discord
- Twitter/X: @algenta_ai
- Docs: https://docs.algenta.ai
- Email: community@algenta.ai
