---
icon: scale-balanced
description: How Algenta licensing works — license types, offline validation, capacity units, and what a license grants for self-hosted and air-gapped use.
---

# Licensing & editions

This page shows operators how Algenta licensing works end to end: how the durable, offline, signed license is issued on an operator box, installed on each runtime machine, and verified locally with no network calls. It covers the air-gapped path, the enforcement flags that are shipped dark today, and how product editions (Codna, Cohenta, Decimas, Escrypto) map to the modules and features a license grants. Everything here is copy-pasteable and grounded in the scripts and runtime the engine actually runs.

## The license model

An Algenta license is a signed JSON Web Token. It is installed at:

```text
~/.algenta/runtime/license.jwt
```

The runtime verifies it **locally on every startup with no network call**. Production and offline licenses are RS256 (asymmetric): the operator box signs with a private key, and each runtime machine verifies with the matching public key. The public key can verify a token; it cannot mint one.

A license carries: plan, device limit, permitted modules, expiry, **product entitlements**, capacity caps, deployment class, and the commercial-use grant. `scripts/issue_offline_license.py` emits this format.

{% hint style="info" %}
The license is a **device entitlement**, not your data plane. The issuer signs license claims only — it never reads customer data, schema data, or runtime payloads. Verification is fully offline; nothing about your repositories or simulations leaves the machine.
{% endhint %}

### Durable across redeploys

The runtime reads the token from the file first. If no file is present, it falls back, in order, to these environment sources — so a hosted or air-gapped engine keeps a valid offline license across redeploys without a persistent volume (the JWT lives in a platform secret):

| Source | Type |
|---|---|
| `~/.algenta/runtime/license.jwt` | file (highest precedence) |
| `ALGENTA_LICENSE_JWT` / `ALGENTA_LOCAL_LICENSE` | inline JWT in an env var |
| `ALGENTA_LICENSE_JWT_FILE` / `ALGENTA_LOCAL_LICENSE_FILE` | path to a JWT file |

Verification is identical regardless of source: RS256, fully offline.

## Issue an offline license (operator box only)

{% hint style="danger" %}
The RS256 private key must **never** live in the repo or on a server. Generate the keypair once, on an offline operator box, and distribute only the public key to runtime machines.
{% endhint %}

{% stepper %}
{% step %}
### Generate the keypair (once, operator box only)

```sh title="generate-keypair.sh"
# Operator box only. Keep algenta-license.key OFF every repo and server.
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out algenta-license.key
openssl rsa -in algenta-license.key -pubout -out algenta-license.pub
```

Distribute **only** `algenta-license.pub` to runtime machines.
{% endstep %}

{% step %}
### Mint a license

Mint with `scripts/issue_offline_license.py`. A typical server deployment (Codna, enterprise plan, one-year validity):

```sh title="mint-license.sh"
EXP=$(( $(date +%s) + 31536000 ))   # +1 year; re-mint before this

python3 scripts/issue_offline_license.py \
  --private-key-file algenta-license.key \
  --device-id "<this machine's device id>" \
  --plan enterprise \
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

The script writes the signed token to `--output` (mode `0600`) and prints a JSON receipt:

```json
{"status": "ok", "output": "license.jwt", "device_id": "<...>", "plan": "enterprise", "algorithm": "RS256"}
```
{% endstep %}

{% step %}
### (Optional) Supply the key by environment variable

You can supply the private key by environment variable instead of `--private-key-file`:

```sh
export ALGENTA_LOCAL_LICENSE_PRIVATE_KEY_FILE=algenta-license.key
python3 scripts/issue_offline_license.py --device-id "<...>" --plan enterprise --output license.jwt
```
{% endstep %}
{% endstepper %}

{% hint style="warning" %}
**`--key-expires-at` is effectively required.** The CLI defaults `--expires-at` to `0` ("no expiry"), and `--key-expires-at` defaults to whatever `--expires-at` is. Omitting both yields `key_expires_at=0`. That token *verifies*, but the stored-offline enforcement sub-path (the `require_local_license`-OFF + enforce-ON profile) **rejects** `key_expires_at <= 0`. Always pass a positive `--key-expires-at`.
{% endhint %}

{% expandable title="Issuer options (full flag reference)" %}
| Flag | Meaning |
|---|---|
| `--device-id` (required) | Target runtime device identifier |
| `--plan` (required) | Plan label, e.g. `enterprise` |
| `--output` (required) | Path to write the signed JWT |
| `--private-key-file` | RSA private key PEM (or `ALGENTA_LOCAL_LICENSE_PRIVATE_KEY_FILE`) |
| `--org-id` | Organization identifier claim |
| `--device-limit` | Max devices; `0` = unlimited |
| `--expires-at` | Unix epoch entitlement expiry; `0` = no expiry |
| `--key-expires-at` | Unix epoch expiry of the backing commercial key; defaults to `--expires-at` |
| `--grace-days` | Offline grace after expiry before a hard block (default `14`) |
| `--permitted-module` | Repeatable; restricts permitted modules (default `*`) |
| `--deployment-class` | `desktop` \| `server` \| `ci` \| `airgapped` \| `oem` |
| `--product-entitlement` | Repeatable `product:tier[:feat1,feat2]` |
| `--products-file` | JSON file mapping products to tiers and features (multi-product editions) |
| `--named-seat-limit` / `--active-node-limit` / `--concurrent-worker-limit` | v2 capacity caps (`0` = unspecified) |
| `--device-allowance-per-seat` | v2 capacity claim |
| `--commercial-use` | Grant commercial use |
| `--offline-grace-days` | v2 offline grace claim |
| `--message` | Operator note embedded in the payload |
{% endexpandable %}

{% expandable title="Multi-product editions with --products-file" %}
For a single license that spans more than one edition, pass a JSON file instead of repeating `--product-entitlement`:

```json title="editions.json"
{
  "codna":   { "tier": "pro",  "features": ["repo_graph", "triage", "simulate", "fix", "apply"] },
  "decimas": { "tier": "team", "features": [] }
}
```

```sh
python3 scripts/issue_offline_license.py \
  --private-key-file algenta-license.key \
  --device-id "<...>" --plan enterprise \
  --deployment-class server \
  --products-file editions.json \
  --key-expires-at "$EXP" --expires-at "$EXP" \
  --output license.jwt
```

`--products-file` and `--product-entitlement` can be combined; entries merge by product name.
{% endexpandable %}

## Install on each runtime machine

Copy the token into place and set the verifying public key:

```sh title="install-license.sh"
mkdir -p ~/.algenta/runtime
cp license.jwt ~/.algenta/runtime/license.jwt

# Inline key, or use the *_FILE form for a path on disk.
export ALGENTA_LOCAL_LICENSE_PUBLIC_KEY="$(cat algenta-license.pub)"
# or:
export ALGENTA_LOCAL_LICENSE_PUBLIC_KEY_FILE=/etc/algenta/algenta-license.pub
```

{% hint style="info" %}
The runtime also accepts `ALGENTA_LICENSE_PUBLIC_KEY` / `ALGENTA_LICENSE_PUBLIC_KEY_FILE` as aliases. Multiple keys are supported (deduplicated) for key rotation.
{% endhint %}

## Verify the gate

`scripts/license_status.py` loads the installed token through the exact `load_license` path the runtime uses — so it verifies precisely what the engine would see. No secrets, no network, no mutation.

A satisfied gate prints `OK` and exits `0`. The same check is available as human-readable text or machine-readable JSON:

{% tabs %}
{% tab title="Text" %}
```sh
python3 scripts/license_status.py
```

```text
OK  license valid=True version=2 source=offline-local plan=enterprise
      deployment_class=server commercial_use=True
      product codna: tier=pro features=apply,fix,repo_graph,simulate,triage
      caps: seats=25 nodes=3 workers=12
      expiry: expires_at=... key_expires_at=... expired=False in_grace=False hard_expired=False
```
{% endtab %}

{% tab title="JSON" %}
```sh
python3 scripts/license_status.py --json
```

```json
{
  "valid": true,
  "source": "offline-local",
  "plan": "enterprise",
  "deployment_class": "server",
  "gate_satisfied": true,
  "products": { "codna": { "tier": "pro", "features": ["apply", "fix", "repo_graph", "simulate", "triage"] } }
}
```
{% endtab %}
{% endtabs %}

Exit codes: `0` = gate satisfied, `1` = not satisfied (invalid, or expired past grace).

| Flag | Effect |
|---|---|
| `--json` | Emit machine-readable JSON |
| `--allow-no-key-expiry` | Accept `key_expires_at <= 0` (only safe under the `require_local_license` path) |

{% hint style="info" %}
If the gate fails, the output tells you why: `not valid` (no installed license or wrong key), `past grace; runtime would block`, or `key_expires_at<=0` (re-mint with `--key-expires-at`). The bottom hint line is the next action.
{% endhint %}

## Enforcement flags (default OFF / dark)

A self-hosted download runs free today. The enforcement machinery is shipped but inert until you opt in. Two flags control it; both default to OFF.

| Env var | Config field | Effect when set |
|---|---|---|
| `ALGENTA_REQUIRE_LOCAL_LICENSE` | `require_local_license` | The runtime requires a valid local signed license; hosted registration and the HS256 dev fallback are disabled. RS256 offline tokens only. |
| `ALGENTA_ENFORCE_LICENSE_VALIDATION` | `enforce_license_validation` | Enables the fail-closed validation path on self-hosted profiles (the dark P5.2 machinery). |

Both are read in `apps/privacy_policy.py` and mirrored into the API config (`apps/api_server/config.py`). With both unset, the engine runs permissively and `license_status.py` is purely informational.

{% hint style="warning" %}
Turning these on is a staged, partly **release-irreversible** rollout (P5.3–P5.7). Do not flip anything before every internal deployment prints `OK` from `scripts/license_status.py`. The full sequence, gate, and rollback are in `docs/LICENSE_ENFORCEMENT_RUNBOOK.md`.
{% endhint %}

## Air-gapped issuance

For machines that will never reach a control plane, mint long-lived tokens with a generous offline grace and the `ci` or `airgapped` deployment class. The token is signed once on the operator box and carried in by file.

{% tabs %}
{% tab title="CI runner" %}
```sh title="mint-ci-license.sh"
EXP=$(( $(date +%s) + 31536000 ))
python3 scripts/issue_offline_license.py \
  --private-key-file algenta-license.key \
  --device-id "$(python3 scripts/license_status.py --json >/dev/null; echo ci-runner-01)" \
  --plan enterprise \
  --deployment-class ci \
  --product-entitlement "codna:pro:repo_graph,triage,simulate,fix,apply" \
  --expires-at "$EXP" --key-expires-at "$EXP" \
  --offline-grace-days 7 \
  --output license.jwt
```
{% endtab %}

{% tab title="Fully air-gapped box" %}
Longer validity, larger grace so an unreachable machine never hard-blocks between maintenance windows:

```sh title="mint-airgapped-license.sh"
EXP=$(( $(date +%s) + 94608000 ))   # +3 years
python3 scripts/issue_offline_license.py \
  --private-key-file algenta-license.key \
  --device-id "<airgapped device id>" \
  --plan enterprise \
  --deployment-class airgapped \
  --product-entitlement "codna:pro:repo_graph,triage,simulate,fix,apply" \
  --expires-at "$EXP" --key-expires-at "$EXP" \
  --grace-days 30 --offline-grace-days 30 \
  --output license.jwt
```
{% endtab %}
{% endtabs %}

Then install the token and public key on the box exactly as above, and confirm with `python3 scripts/license_status.py`. No network is required at any step.

## Editions and permitted modules

Algenta is the engine; each product is a curated **edition** over the same MCP/API core. A license grants per-product **features**, and the local engine maps each granted feature to the concrete tools it unlocks:

```text
available_tools = installed ∩ product_allowlist ∩ license_feature_tools
```

The canonical registry lives at `packages/mcp/algenta_mcp/products.py`.

| Edition | Product key | Status | Feature buckets (Codna) |
|---|---|---|---|
| Codna (coding) | `codna` | Shipped | `repo_graph`, `triage`, `simulate`, `fix`, `apply` |
| Cohenta (marketing) | `cohenta` | Reserved (empty, fails closed) | — |
| Decimas (trading) | `decimas` | Reserved (empty, fails closed) | — |
| Escrypto (crypto governance) | `escrypto` | Reserved (empty, fails closed) | — |

The Codna feature buckets map to tools as follows:

| Feature | Tools unlocked |
|---|---|
| base (always) | `get_me`, `get_limits`, `get_usage`, `get_repository_intelligence_capabilities` |
| `repo_graph` | `query_repository_graph`, `create_repository_snapshot`, `get_repository_snapshot` |
| `triage` | `triage_repository`, `create_repository_decision_plan` |
| `simulate` | `simulate_repository`, `simulate_repository_patch`, `simulate`, `plan_decision`, `recommend`, `log_decision`, `list_decisions`, `get_decision`, `record_outcome` |
| `fix` | `run_repository_fix`, `run_repository_pipeline`, `create_agent_run`, `get_agent_run`, `get_agent_run_events`, `cancel_agent_run` |
| `apply` | `apply_repository` |

A license granting all five features (`codna:pro:repo_graph,triage,simulate,fix,apply`) yields the full Codna edition. A narrower grant exposes only those tools.

{% hint style="info" %}
The product selector (`X-Algenta-Product` / `ALGENTA_PRODUCT`) is a routing hint, not authorization. Visibility is the intersection of the product allowlist, the verified key's entitlements, organization policy, and the license's feature grants. An unknown or unentitled product resolves to the **empty** set — never the full registry.
{% endhint %}

{% expandable title="Advanced: the --permitted-module claim" %}
The `--permitted-module` claim is a coarse engine-module allowlist (default `*` = all modules). Product entitlements are the precise mechanism; reach for `--permitted-module` only when you deliberately want a blunt module restriction independent of editions.
{% endexpandable %}

## Open-core terms (ACL 1.0)

Self-hosting is governed by the Algenta Community License (ACL) 1.0, in `LICENSE` at the repo root. In plain terms:

- **Community Use is free** — non-commercial use, personal projects, research, education, open-source work, and internal business operations at organizations with **fewer than 50 employees AND under $5,000,000 USD annual gross revenue**.
- **Commercial Self-Hosting** — deploying Algenta inside a product or service offered to external customers, or use by organizations above those thresholds — requires a paid commercial license.
- The framework, integrations, portal, and SDKs are source-available; the compiled Mojo engine binary (`mojo_build/simulate`) ships under a separate binary license and may be redistributed for Community Use only.

{% hint style="success" %}
The signed license described on this page is the **enforcement** mechanism (per-machine, offline, fail-closed) that backs those commercial terms once enabled. Enforcement and pricing are independent: a license can be present and verified long before any enforcement flag is flipped.
{% endhint %}

{% expandable title="See also (source of truth on disk)" %}
- `docs/LICENSE_ENFORCEMENT_RUNBOOK.md` — the full P5 fail-closed rollout, the go/no-go gate, the irreversible flips (P5.3–P5.7), and rollback.
- `scripts/issue_offline_license.py` — the offline issuer (operator box only).
- `scripts/license_status.py` — the local verification gate.
- `LICENSE` — ACL 1.0 open-core terms and thresholds.
{% endexpandable %}

## Related pages

{% content-ref url="self-hosting.md" %}
[self-hosting.md](self-hosting.md)
{% endcontent-ref %}

{% content-ref url="billing.md" %}
[billing.md](billing.md)
{% endcontent-ref %}

{% content-ref url="authentication.md" %}
[authentication.md](authentication.md)
{% endcontent-ref %}

{% content-ref url="troubleshooting.md" %}
[troubleshooting.md](troubleshooting.md)
{% endcontent-ref %}
