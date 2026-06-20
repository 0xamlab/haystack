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
EXP=$(( $(date +%s) + 31536000 ))   # +1y; renew/re-mint before this
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
  --expires-at "$EXP" --key-expires-at "$EXP" \
  --offline-grace-days 3 \
  --output license.jwt
```

> **`--key-expires-at` is REQUIRED, not optional.** The CLI defaults `--expires-at` to `0`
> ("no expiry") and `--key-expires-at` to whatever `--expires-at` is — so omitting both yields
> `key_expires_at=0`. Such a token *verifies* (and older `license_status.py` reported `OK`), but
> the `stored_offline_execution_entitlement` enforcement sub-path (the `require_local_license`-OFF
> + enforce-ON profile) **rejects** `key_expires_at <= 0`. Always pass a positive `--key-expires-at`.
> (`scripts/license_status.py` now fails the gate on `key_expires_at<=0`; `--allow-no-key-expiry`
> overrides it only when the deployment will run exclusively under `require_local_license`.)

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

| Step | Change | Anchor(s) | If wrong, exposure |
|---|---|---|---|
| **P5.3** | Replace the `ALGENTA_REQUIRE_LOCAL_LICENSE` env bypass with a **release-excluded build flag** + test-only signing key; flip the default **ON** for self-hosted release profiles; drop the HS256 fallback in release. | env read `privacy_policy.py:412`; resolve `:303`; runtime gate `license.py:96`; dev key `license.py:60` (`_DEV_SECRET`); HS256 loop `license.py:541`; API mirror `config.py:90` | A machine without a valid v2 license goes inert — caught by P5.1 if the gate was honored. |
| **P5.4** | Close the free-self-host grant. **The real branch is `credits.py:256-262`** (`_offline_execution_entitled`'s `return True`), *not* `privacy_policy.py` (the plan's cited line was wrong; `privacy_policy.py:475` helper is dead code). | `credits.py:261` (the grant); sole caller `credits.py:286` | Same as P5.3; removes the last permissive path. |
| **P5.5** | Add + honor `ALGENTA_V1_LICENSE_SUNSET` (**greenfield — no code reads it today**); past the cutoff `_parse_token`/`load_license` **reject** v1. | `license.py:342` (`is_legacy_v1`); `:399` (`ver` default 1); reject in `:505` + `:949` | Any still-v1 deployment goes inert — re-mint as v2 (P5.1) first. |
| **P5.6** | Make the verifier **RS256-only** in prod (reject HS256/`alg=none`; require recognized `kid`; pin `iss`) in **both** `_parse_token` *and* the CRL `_verify_control_plane_jwt`. | `license.py:519` (RS256), `:541` (HS256), `:582`+`:596` (CRL); `:100` (`_offline_license_public_keys` carry **no kid**) | A non-RS256/dev token stops verifying; **requiring `kid` breaks every offline token** (issuer emits none) — see prereqs. |
| **P5.7** | **Require `aud`**: emit `aud` on issuance and flip the four decode sites to `verify_aud=True` + `audience="device-license"` (P5.2 made them *accept* aud; this makes it *required*). | decode sites `license.py:526/547/586/599`; issuers `device_service.py:556`, `issue_offline_license.py`, `_issue_dev_jwt` `license.py:462`, CRL `device_service.py:1012` | Any token minted before aud-emission stops verifying — re-mint with the aud claim. |

### Prerequisites surfaced by the readiness audit (do these *inside* the relevant PR, before the flip lands)

- **P5.3 is bigger than one flag.** `enforce_license_validation` has exactly **one** consumer today — `credits.py:261` (the credits/execution path). Flipping its default ON does **not** by itself make the **daemon** (`daemon.py:126`) or the **pure-local `Runtime()`** (`runtime_local_limits.py:50`) fail closed — those still gate on `require_local_license`. So "self-hosted release = inert without a license" requires **either** flipping `require_local_license`'s default for release profiles **or** wiring `enforce_license_validation` into `daemon.py:126` + `runtime_local_limits.py:50`. Decide explicitly; don't assume the one flag covers all entry points.
- **P5.6 `kid`:** `issue_offline_license.py` emits no `kid` header and `_offline_license_public_keys()` carries no `kid`. Requiring `kid` means first adding a `kid` header to the issuer + JWKS selection on the offline path, then re-minting (P5.1) **before** the flip. Pin `iss` to accept **both** `algenta-control-plane` and `algenta-offline-license`.
- **P5.7 `aud`:** today the intended `audience="device-license"` is placed in the `sub` claim, not `aud` — no issuer emits `aud`. Add `aud` to **all** issuers (control-plane `_issue_license_jwt`, offline CLI, dev stub, CRL) and re-mint/propagate **before** flipping `verify_aud=True`, or every installed token fails.

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
