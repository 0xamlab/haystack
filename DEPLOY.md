# Deploying the codna engine — Fly.io + Cloudflare

Production hosting for the engine (which serves the codna GitHub App). Origin stack is Fly-native;
Cloudflare is the edge. Everything here is repo-defined and runs from the terminal (`flyctl`,
`tofu`/`terraform`, optional `wrangler`). The console is only needed for account/billing and
creating scoped API tokens.

> The GitHub App surface is **inert until `GITHUB_APP_*` is set**, so deploying without those
> secrets is safe — it just won't process webhooks yet.

## Topology (v1)
```
user → Cloudflare edge (DNS · TLS Full-Strict · WAF · rate-limit · static-only cache)
     → codna-api      (Fly, public :8000, warm, behind CF)        image: …/api
     → codna-engine   (Fly, ONE Machine + volume, private)        image: …/engine
            ├ celery worker  (queues: persist,simulate,repository)
            └ agent-core sidecar :8787  (shared /home/app/.algenta volume)
     → Fly Managed Postgres · Upstash Redis · Tigris Object Storage
```
**Why api and engine are split, but worker+sidecar are not:** the agent-core contract is
shared-filesystem — the worker materializes a repo `working_dir` and the sidecar mutates that same
path. A Fly volume attaches to one Machine, so worker+sidecar must co-locate (the combined
`Dockerfile.engine.prod`). The api is stateless (it enqueues to the engine) and scales on its own.

## Prerequisites (console, one-time)
- Fly.io account + org + `FLY_API_TOKEN`; Cloudflare account with the `codna.ai` zone + an API token
  (`CLOUDFLARE_API_TOKEN`) with DNS + Ruleset edit.
- `flyctl`, `tofu` (or `terraform`) installed. `export FLY_API_TOKEN=…`.
- Images in GHCR: CI builds `…/api`, `…/worker`, `…/engine` on push to main. The **engine** image
  FROMs the private codna sidecar — give CI a `CODNA_GHCR_READ_TOKEN` secret (PAT w/ read:packages on
  thyn-ai/codna) **or** make that package public, else the engine build is skipped.
- Register the GitHub App (below) to get the `GITHUB_APP_*` values.

## 1. Bootstrap (idempotent)
```bash
export FLY_API_TOKEN=…              # from .env / your secret manager
make bootstrap
```
Creates the 2 Fly apps, Fly Managed Postgres (attached → `DATABASE_URL`), Upstash Redis, a Tigris
bucket, the engine volume (`codna_engine_data` → `/home/app/.algenta`), and requests the Fly cert for
`api.codna.ai`. Re-runnable. It prints which secrets are still missing.

> **Tigris → engine env remap:** Fly/Tigris injects `AWS_*` + `BUCKET_NAME`. The engine only reads
> `S3_*`, so set on **both** apps:
> `S3_ENDPOINT_URL=$AWS_ENDPOINT_URL_S3  S3_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID
> S3_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY  S3_BUCKET_NAME=$BUCKET_NAME  S3_REGION=auto`
> plus `ALGENTA_RI_OBJECT_STORE=s3`.

## 2. Secrets (`flyctl secrets set -a <app> …`)
**Both apps:** `DATABASE_URL`, `DATABASE_URL_SYNC`, `REDIS_URL`, the `S3_*` set above,
`ALGENTA_CONFIG_ENCRYPTION_KEY` (64-hex), `ALGENTA_AGENT_CORE_TOKEN` (the bearer the api/worker send),
GitHub App secrets (`GITHUB_APP_ID/PRIVATE_KEY/WEBHOOK_SECRET/CLIENT_ID/CLIENT_SECRET/SLUG`).
**codna-api only:** `ALGENTA_ENGINE_URL=https://api.codna.ai`, `ALGENTA_ENGINE_API_KEY`, `JWT_SECRET`,
`WEBHOOK_SIGNING_SECRET`.
**codna-engine only:** `AGENT_CORE_AUTH_TOKEN` (= the same value as `ALGENTA_AGENT_CORE_TOKEN`; the
sidecar verifies it), `AGENT_CORE_REQUIRE_AUTH=1`, the **LLM key** (`ANTHROPIC_API_KEY` /
`OPENAI_API_KEY` — Cline runs here), `ALGENTA_ENGINE_URL=https://api.codna.ai`, `ALGENTA_ENGINE_API_KEY`.
If egress runs fail-closed, set `ALGENTA_EGRESS_ALLOWLIST` (see below).

`make status` reports any missing required secret per app.

## 3. Deploy
```bash
make deploy-fly         # engine first (sidecar up), then api (runs `alembic upgrade head`)
make deploy-cloudflare  # tofu apply: DNS, TLS Full-Strict, cache rules, WAF/rate-limit
make status             # fly status + /v1/health + secrets check
# or: make deploy       # both, then status
```
Pin a specific build with `make deploy-fly TAG=git-<sha>` (default = HEAD short sha).

### Cloudflare cert ordering (Full-Strict)
Full-Strict requires a valid **Fly** origin cert for `api.codna.ai` first, and the orange cloud can
intercept Fly's ACME challenge. Sequence:
1. `fly certs add api.codna.ai -a codna-api` (done by bootstrap).
2. First `tofu apply` with `-var api_proxied=false` (grey) so the challenge reaches Fly.
3. When `fly certs show api.codna.ai -a codna-api` is **Ready**, `tofu apply` with `api_proxied=true`
   (orange) — `tls.tf` already sets SSL=Full-Strict.

## 4. Register the GitHub App
- Webhook URL `https://api.codna.ai/webhooks/github`; OAuth callback
  `https://api.codna.ai/github/app/install/callback`; **enable "Request user authorization during
  installation"** (the callback verifies the installer is an admin via OAuth).
- Permissions: Contents `R/W`, Pull requests `R/W`, Issues `R/W`, Checks `Read`, Metadata `Read`.
- Subscribe to events: `check_suite`, `issues`, `pull_request_review`.
- Put the App ID / private key / client id+secret / webhook secret / slug into the Fly secrets, redeploy.

## 5. Verify
1. `curl -i https://api.codna.ai/v1/health` → `200`.
2. Install on a sandbox repo → fail a CI check → codna opens a fix PR.
3. Label an issue `codna-fix` → codna opens a PR.
4. Re-deliver a webhook → no second PR (durable dedupe).
5. `make bench-gate` → p90 < 15ms. **Scope:** the warm-engine hot path, not the multi-minute fix.

## Egress allowlist (only if egress is global fail-closed)
Start `github.com,api.github.com`, then add what the fix pipeline fetches: `codeload.github.com`,
`raw.githubusercontent.com`, `objects.githubusercontent.com`, the LLM host(s), and the Tigris +
Upstash endpoints. Default SaaS mode (outbound allowed) needs none of this.

## Ops
`make logs APP=api|engine` · `make status` · `make rollback APP=api|engine TAG=git-<sha>`
(list candidates with `fly releases -a codna-api`).

## Known verify-items (first real deploy)
- **Combined image:** confirm `bun` lands at `/usr/local/bin/bun` in the codna sidecar base and
  `/app/agent-core` runs via `bun run-server.mjs` (it does in `Dockerfile.sidecar`); a `docker build
  -f infra/docker/Dockerfile.engine.prod .` exercises it.
- **OpenTofu:** `cd infra/cloudflare && tofu validate` once the provider is downloaded; the WAF
  managed-ruleset + advanced rate-limit need a paid Cloudflare plan (`tofu plan` shows what your plan
  allows).
- **`fly postgres`/`fly redis`/`fly storage`** CLIs vary by flyctl version; if a command is absent,
  provision in the console and set the corresponding secrets — `make bootstrap` degrades gracefully.
- Do not scale `codna-engine` past 1 Machine (one volume, shared working dir).
