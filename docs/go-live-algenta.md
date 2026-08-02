---
icon: rocket
description: Owner-only sequencing, launch gates, and credential-safe steps for taking Algenta live.
---

# Taking Algenta live — owner runbook

Internal engineering runbook (NOT for gitbook/ — it names dark flags, license minting, and secrets). It
covers the merge sequencing for the go-live PR series, the owner-only steps, and the launch-gate checklist.

Architecture: **Shared Engine, Product-Scoped Control Plane.** One deployed engine; brands (codna / telys /
algenta) are *products* separated by identity / entitlement / billing / license claims — never duplicated
infra. `api.codna.ai` / `api.telys.ai` / `api.algenta.ai` are DNS aliases in front of the same Fly engine;
product is resolved from the client_id / plan namespace / license claim, consolidated in
`apps/api_server/services/product_registry.py`.

## The PR series

| PR | Phase | What | Merge state |
|---|---|---|---|
| thyn-ai/algenta#288 | 0+1 | Product registry + algenta device-login / onboard / tiers / `0049` migration / license routing (+ adversarial-review hardening) | base `main` |
| thyn-ai/accounts#31 | 2 | Portal registers `algenta` (deviceProxy + apps.ts + env) | base `main` |
| thyn-ai/algenta#289 | 3 | Product-scoped Stripe, **gated dark** + cross-brand isolation | **stacked on #288** |
| thyn-ai/algenta#290 | 4 | `algenta-mcp` → Official MCP Registry (Cursor/Codex/Claude) | base `main` |
| thyn-ai/algenta#291 | 6 | 100-year OEM minter + golden tests | base `main` |
| thyn-ai/algenta#292 | 5 | Graduate the local runtime into `algenta` with an automatically installed native engine | base `main` |

### Merge order (avoid stranding the stacked PR)
1. Merge **#288** (squash).
2. `git checkout feat/algenta-stripe && git rebase origin/main && git push --force-with-lease` — #289 auto-retargets to `main` and its diff collapses to just Phase 3. Merge **#289**.
3. Merge **#290**, **#291**, **#292** in any order (all base `main`). #292 + #290 both touch `release-sdks.yml`; resolve the build-loop conflict using `python-sdk algenta mcp`.
4. Merge **accounts#31** (independent repo).

CI note: `build-runtime.yml` is dispatch/tag-only (it needs the Mojo toolchain + `ALGENTA_SIGNING_KEY`), so it does not gate any PR.

CI note (memory): `mojo build` is the memory-hungry part of that workflow. Measured on the hosted linux runner: **7.8 GiB RAM + a 3.0 GiB stock swapfile = a 10.8 GiB ceiling**, while the heaviest 24-module shard (the `optimization.*` range) peaks at **11.3 GiB**. Under that ceiling the runner VM is torn down mid-shard and the step reports only `exit code 143` + "The runner has received a shutdown signal". The linux arm therefore reclaims the preinstalled Android/Haskell/.NET/Swift/Docker content (there is no `/mnt` scratch disk on this image and `/` starts with only ~12 GiB free) and spends it on a 24 GiB swapfile, then publishes a per-shard footprint ceiling of 80% of the resulting RAM+swap. The builder prints host memory up front, announces each shard **before** compiling it, and reports each shard's peak footprint and elapsed time, so a recurrence names the shard instead of leaving it to be inferred. If the peak ever approaches that ceiling, add headroom (or move to a larger runner) rather than raising the ceiling.

## Owner steps (in order)

### 1. Deploy the engine + the algenta host
- `fly certs add api.algenta.ai` on the shared engine app (`codna-api`). Add the Cloudflare DNS record (Full-Strict), per `DEPLOY.md §3`.
- Deploy `main` (Makefile `deploy` / `.github/workflows/deploy.yml`; needs `FLY_API_TOKEN` + `CODNA_GHCR_READ_TOKEN`).
- Fly secrets: `ALGENTA_ACCOUNTS_BASE_URL=https://accounts.thyn.ai` (device-login verification_uri), the license public key, and the Stripe secrets below.

### 2. Accounts portal (Vercel)
- Merge accounts#31. Set `NEXT_PUBLIC_API_URL_ALGENTA=https://api.algenta.ai` in Vercel (defaults to that anyway).
- Enable the GitHub/Google providers on the shared Supabase project (`qxxnqenpvutophhcmebr`) if not already.
- Optional: add `public/assets/logo/algenta-mark.svg` (until then the name wordmark is used).

### 3. Stripe (Phase 3 — currently DARK)
- In Stripe, create the Algenta products/prices **tagged `metadata.source=algenta`**: `algenta_pro`, `algenta_team`.
- Set Fly secrets `STRIPE_PRICE_ALGENTA_PRO` / `STRIPE_PRICE_ALGENTA_TEAM`; point a webhook at `https://api.algenta.ai/v1/billing/webhook`.
- Verify in **Stripe test mode** first (checkout → webhook → `org.plan=algenta_pro`).
- Flip billing on: set `algenta.billing → True` in `product_registry.py` (the checkout gate returns `403 billing_not_enabled` until then). Ship that as a one-line PR.

### 4. SDKs + MCP to PyPI (Phases 4 + 5)
- Set the repo secret **`PYPI_TOKEN`** = a PyPI API token with upload rights for `algenta-sdk` and `algenta-mcp`. `algenta` and `algenta-runtime-native` are released together by the runtime workflow. Optional `TEST_PYPI_TOKEN` supports the TestPyPI rehearsal.
- **Native runtime first:** provide the C-ABI Mojo source (`mojo/engine/algenta_runtime.mojo`, exporting `algenta_runtime_{version,platform,init,execute,free,shutdown}` — see `packages/algenta/algenta/native/loader.py`), set the `ALGENTA_SIGNING_KEY` secret that matches the committed `algenta_release_pub.pem`, and verify the committed `algenta_license_pub.pem` still matches the production signer JWKS. Run `build-runtime.yml` (per-platform) → it compiles, signs, and builds the `algenta-runtime-native` wheels; the **clean-machine contract** job must pass.
- Then `release-sdks.yml` (TestPyPI rehearsal → PyPI) for `algenta-sdk` and `algenta-mcp`.
- **Do NOT publish a public `algenta` release until a `algenta-runtime-native` wheel for that platform contains the signed native runtime** (else `pip install algenta` fails to resolve the sidecar — which is the intended fail-safe, but confirm the supported platforms are live first).
- After `algenta-mcp` is live on PyPI, dispatch `publish-mcp.yml` (registers `io.github.thyn-ai/algenta` via OIDC).

### 5. OEM licenses (Phase 6 — protect the current setup)
- With `dist-keys/platform_license_priv.pem` (the shared platform key), mint 100-year OEM licenses for the sub-brands — dry-run first, then real behind an allowlist:
  ```bash
  python scripts/issue_oem_license.py --product codna  --customer codna  --tier team --exp-years 100 --out dist/oem/codna-license.jwt
  python scripts/issue_oem_license.py --product telys  --customer telys  --tier team --exp-years 100 --out dist/oem/telys-license.jwt
  # ... cohenta / decimas / escrypto / mission as needed
  ```
- Each is self-verified against the strict platform contract + emits a `.audit.json`. **Deliver over a secure channel; never commit a token.**

## Launch gates (verify each)

1. `curl https://api.algenta.ai/v1/health` → 200.
2. **`api.codna.ai` + `api.telys.ai` existing smoke tests still pass** (regression = blocker). Covered by the shared-file adversarial review + fresh-DB test runs in #288/#289.
3. Clean-machine `algenta login` works (fresh box, no toolchain).
4. `algenta login` is idempotent (repeat → same org, no junk).
5. Free onboarding creates only the correct `algenta_free` entitlement (`test_product_onboard`).
6. Stripe checkout upgrades only the intended Algenta org/product (isolation tests in #289); a codna/telys webhook can't mutate algenta.
7. `algenta-mcp` appears in Cursor / Codex / Claude (stdio) after `publish-mcp.yml`.
8. pip-installed `algenta` uses the bundled in-process sidecar runtime (`algenta runtime doctor` → source `bundled sidecar`, mode `in-process`).
9. `lsof -p "$ALGENTA_PID"` shows no local TCP listeners for the CLI runtime path (doctor: `tcp listeners: none`).
10. **Existing codna/telys licenses still verify** after deploy (OEM golden tests, one shared verifier).
11. New 100y OEM license verifies across old + new verifiers.
12. Wrong-product / wrong-audience / wrong-issuer / expired license + cross-product billing all rejected (golden + Stripe isolation tests).
13. `which mojo` / `which modular` may return nothing, yet `algenta runtime doctor` passes.
14. The release `algenta-runtime-native` wheel CONTAINS the native runtime and does NOT compile/download it on install.
15. `algenta-mcp` starts + lists tools without importing/loading the native runtime (thin-bridge boundary test).
16. On an unsupported platform, `pip install algenta` fails at pip resolution (no matching `algenta-runtime-native` wheel) — never a broken install that later asks for Mojo.
17. The clean-machine contract CI job (in `build-runtime.yml`) passes.

## Next step

Execute every launch gate in order and attach the command output to the release record; any failed gate blocks publication.
