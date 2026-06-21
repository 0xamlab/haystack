---
icon: scale-balanced
description: How Algenta licensing works for self-hosted and air-gapped use — what a license grants, how to install and verify it offline, the editions, and the open-core terms.
---

# Licensing & editions

This page explains how Algenta licensing works for self-hosted and air-gapped deployments: what a license grants, how you install and verify it locally with no network calls, how product editions map to features, and the open-core terms.

{% hint style="info" %}
**Community Use needs no license.** A self-hosted download runs under the open-core [Community License](#open-core-terms-acl-1-0) without any license file. You only install a license for commercial use or to unlock a paid edition.
{% endhint %}

## The license model

An Algenta license is a signed JSON Web Token. It is installed at:

```text
~/.algenta/runtime/license.jwt
```

The runtime verifies it **locally on every startup with no network call**. Licenses are RS256 (asymmetric): Algenta signs your license with a private key, and each of your runtime machines verifies it with the matching public key you are given. A public key can verify a token; it cannot create one.

A license carries: plan, device limit, permitted modules, expiry, **product entitlements**, capacity caps, deployment class, and the commercial-use grant.

{% hint style="info" %}
The license is a **device entitlement**, not your data plane. It carries signed claims only — it never reads customer data, schema data, or runtime payloads. Verification is fully offline; nothing about your repositories or simulations leaves the machine.
{% endhint %}

### Durable across redeploys

The runtime reads the token from the file first. If no file is present, it falls back, in order, to these environment sources — so a hosted or air-gapped engine keeps a valid license across redeploys without a persistent volume (the JWT lives in a platform secret):

| Source | Type |
|---|---|
| `~/.algenta/runtime/license.jwt` | file (highest precedence) |
| `ALGENTA_LICENSE_JWT` / `ALGENTA_LOCAL_LICENSE` | inline JWT in an env var |
| `ALGENTA_LICENSE_JWT_FILE` / `ALGENTA_LOCAL_LICENSE_FILE` | path to a JWT file |

Verification is identical regardless of source: RS256, fully offline.

## Install a license

Algenta issues you a signed license file (`license.jwt`) and the matching **public key** for verification. Install both on each runtime machine:

```sh title="install-license.sh"
mkdir -p ~/.algenta/runtime
cp license.jwt ~/.algenta/runtime/license.jwt

# Inline key, or use the *_FILE form for a path on disk.
export ALGENTA_LOCAL_LICENSE_PUBLIC_KEY="$(cat algenta-license.pub)"
# or:
export ALGENTA_LOCAL_LICENSE_PUBLIC_KEY_FILE=/etc/algenta/algenta-license.pub
```

{% hint style="info" %}
The runtime also accepts `ALGENTA_LICENSE_PUBLIC_KEY` / `ALGENTA_LICENSE_PUBLIC_KEY_FILE` as aliases. Multiple keys are supported (deduplicated) so you can rotate keys without downtime.
{% endhint %}

For an air-gapped machine, copy the same two files in by hand — no network is required at any step. See [Run air-gapped](guides/air-gapped.md).

## Verify it locally

`scripts/license_status.py` loads the installed token through the exact path the runtime uses, so it verifies precisely what the engine would see. No secrets, no network, no mutation.

A satisfied gate prints `OK` and exits `0`. The check is available as human-readable text or machine-readable JSON:

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

Exit codes: `0` = the license is valid, `1` = not valid (missing, wrong key, or expired past grace).

{% hint style="info" %}
**Expected result:** `OK` and exit `0`. If it fails, the output names the cause — no installed license, the wrong public key, or expired past grace. The bottom hint line is the next action; if your license has expired, request a renewed one.
{% endhint %}

## Editions and features

Algenta is the engine; each product is a curated **edition** over the same MCP/API core. A license grants per-product **features**, and the local engine maps each granted feature to the concrete tools it unlocks:

```text
available_tools = installed ∩ product_allowlist ∩ license_feature_tools
```

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

## Open-core terms (ACL 1.0)

Self-hosting is governed by the Algenta Community License (ACL) 1.0, in `LICENSE` at the repo root. In plain terms:

- **Community Use is free** — non-commercial use, personal projects, research, education, open-source work, and internal business operations at organizations with **fewer than 50 employees AND under $5,000,000 USD annual gross revenue**.
- **Commercial Self-Hosting** — deploying Algenta inside a product or service offered to external customers, or use by organizations above those thresholds — requires a paid commercial license.
- The framework, integrations, portal, and SDKs are source-available; the compiled Mojo engine binary (`mojo_build/simulate`) ships under a separate binary license and may be redistributed for Community Use only.

The signed license described on this page is the per-machine, offline mechanism that backs the commercial terms.

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
