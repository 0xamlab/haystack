# License enforcement — fail-closed rollout runbook (P5)

> **Audience:** the Algenta owner/operator. This is the irreversible part of the licensing
> plan. Work top-to-bottom; do **not** skip the gate. Enforcement (per-machine copy
> protection) is separate from pricing — this runbook is about turning enforcement *on*,
> not about seats/nodes/workers (those are control-plane concerns).

## What "flipping" actually does

Today a self-hosted download runs free: `privacy_policy.enforce_license_validation`
defaults **OFF** (shipped dark in P5.2, PR #216), and `ALGENTA_REQUIRE_LOCAL_LICENSE` can
disable the local-license requirement. After the flip (P5.3–P5.7) a release build is
**inert without a valid v2 license** and there is no env var to re-enable it.

Because that is release-irreversible, **every internal deployment must already carry a
valid v2 license before any flip.** That is P5.1, and the gate is `scripts/license_status.py`.

---

## P5.0 — keys (one-time)

The RS256 **private key never lives in the repo or on Fly.** It lives only in the
Cloudflare `license-signer` Worker secret (production issuance) or on an offline operator
box (internal/air-gapped issuance via `issue_offline_license.py`).

```sh
# Operator box only. Keep algenta-license.key OFF every repo and server.
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out algenta-license.key
openssl rsa -in algenta-license.key -pubout -out algenta-license.pub
```

Distribute **only** `algenta-license.pub` to runtime machines (it verifies tokens; it
cannot mint them). The Worker already publishes the same key at
`https://license.algenta.ai/.well-known/jwks.json`.

---

## P5.1 — mint + install internal v2 licenses (REVERSIBLE; do this first)

Mint a v2 license per internal deployment — **Mission, Codna, Cohenta, CI**, plus any other
machine running the engine. Example (server deployment, Codna pro):

```sh
python3 scripts/issue_offline_license.py \
  --private-key-file algenta-license.key \
  --device-id "<this machine's device id>" \
  --plan enterprise \
  --license-version 2 \
  --deployment-class server \
  --org-id org_algenta_internal \
  --license-id lic_codna_prod \
  --entitlement-version 1 \
  --product-entitlement "codna:pro:repo_graph,triage,simulate,fix,apply" \
  --named-seat-limit 25 --active-node-limit 3 --concurrent-worker-limit 12 \
  --commercial-use \
  --offline-grace-days 3 \
  --output license.jwt
```

(CI runners get `--deployment-class ci`; air-gapped boxes get a long `--expires-at` +
larger `--offline-grace-days`. Use `--products-file` for multi-product editions.)

**Install** on the target machine:

```sh
mkdir -p ~/.algenta/runtime
cp license.jwt ~/.algenta/runtime/license.jwt
export ALGENTA_LOCAL_LICENSE_PUBLIC_KEY="$(cat algenta-license.pub)"   # or *_FILE=path
```

**Verify the gate** (this is the go/no-go):

```sh
python3 scripts/license_status.py        # expect: OK ... version=2 ... ; exit 0
```

Repeat for every machine. **Do not proceed past this point until every internal
deployment prints `OK` (exit 0).** This step installs files only — fully reversible by
removing `~/.algenta/runtime/license.jwt`.

---

## Gate

```
✅ Cloudflare Worker deployed, JWKS reachable (P4b)
✅ All internal deployments: scripts/license_status.py → OK (P5.1)
↓ only then
```

---

## P5.3–P5.7 — the irreversible flips (release-irreversible; one PR each, staged)

Ship these **only after the gate is green**, one at a time, watching each deployment's
`license_status.py` between steps. Each is a separate reviewed PR.

| Step | Change | If wrong, exposure |
|---|---|---|
| **P5.3** | Replace `ALGENTA_REQUIRE_LOCAL_LICENSE=0` with a **release-excluded build flag** + test-only signing key; flip `enforce_license_validation` default **ON** for downloaded/self-hosted release profiles. Drop the HS256 verification fallback in release. | A machine without a valid v2 license goes inert — caught by P5.1 if the gate was honored. |
| **P5.4** | Close the free-self-host branch in `privacy_policy.py` (`private_profile`/self-hosted permissive path) + audit callers. Download with no Algenta license = inert. | Same as P5.3; this removes the last permissive path. |
| **P5.5** | Set `ALGENTA_V1_LICENSE_SUNSET`; past the cutoff, `load_license`/`_parse_token` **reject** v1 tokens (no more legacy-permissive). v2-only thereafter. | Any still-v1 deployment goes inert — re-mint as v2 (P5.1) first. |
| **P5.6** | Make the signer + verifier **RS256-only** in production (reject HS256/`alg=none`/unexpected alg; require a recognized `kid`; pin `iss`). | A token signed with a non-RS256/dev path stops verifying. |
| **P5.7** | **Require `aud`**: emit `aud` on issuance and flip verification to `verify_aud=True` + `audience="device-license"` (P5.2 already made the verifier *accept* aud; this makes it *required*). Pin `iss`+`aud` together. | Tokens minted before aud-emission stop verifying — re-mint with the aud claim. |

### Rollback

P5.1 is fully reversible (delete the installed token). P5.3–P5.7 are **release-irreversible**
for any release already shipped — a published fail-closed build cannot be made permissive by
config. To recover a *running* fleet, install valid v2 licenses (P5.1) rather than trying to
disable enforcement. Roll back the *source* before cutting a new release if a step proves wrong.

---

## Verification (end-to-end, after P5.7)

1. Clean machine, no license, **release build** → `Runtime()` + daemon refuse; no env var re-enables them.
2. Install a valid v2 license → work resumes.
3. v1 token past `ALGENTA_V1_LICENSE_SUNSET` → rejected.
4. HS256 / `alg=none` / bad `kid` / bad `aud` → rejected; valid RS256 + `kid` + `aud` offline → accepted.
5. `scripts/self_host_smoke.sh` / `self_host_persistence_proof.sh` pass with a license, fail-closed without.
