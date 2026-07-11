---
icon: network-wired
description: Run Algenta fully air-gapped with no outbound network — install and verify an offline RS256 license, prove the egress policy fails closed, and set the engine for no-LLM or BYOK operation.
---

# Run Algenta air-gapped

This guide takes a self-hosted Algenta deployment fully offline: **no phone home**, no control-plane calls, no telemetry egress, and no managed LLM. You will install a signed offline license that verifies with no network, set the deployment to the strict `air_gapped` privacy profile, confirm the egress policy fails closed, and choose how the engine handles LLM work when nothing can leave the network.

Air-gapped operation rests on three independent facts about the engine:

* **Offline license verification.** The runtime validates an RS256-signed JWT locally on every startup using a public key you provide — there is no network round-trip to authorize execution. (Hosted deployments exchange an API key for a license once, then run offline; an air-gapped box skips even that by being pre-provisioned with a signed file.)
* **A self-hosted engine.** The API and its bundled compute runtime run entirely on your host. Computation never depends on a remote service.
* **No telemetry egress.** In a private profile, vendor telemetry and Algenta-cloud destinations are disabled by construction, and every outbound request is classified and denied unless explicitly allowlisted.

{% hint style="info" %}
The `air_gapped` mode is the strict sibling of `self_hosted`. Both disable cloud, disable telemetry, and refuse outbound network by default. `air_gapped` goes further: it **requires** a local signed license and **forbids** any `control_plane_sync` telemetry or metering, so a misconfiguration cannot silently re-enable a call home. See [Deployment modes & privacy](../concepts/deployment-modes.md).
{% endhint %}

## Prerequisites

* A working self-hosted install on the isolated host (see [Self-hosting](../self-hosting.md)).
* A healthy self-hosted Algenta deployment. The bundled runtime starts with the service; verify it on [Verify the bundled engine](../engine/bundled-runtime.md).
* An offline license **issued by Algenta** for this host, plus the matching **public key** that verifies it. Only the signed license file and the public key cross the air gap. (Community Use needs no license — see [Licensing](../licensing.md).)

## Install the offline license

An air-gapped license is bound to the host's device identity and verified locally with no network. You read the device id on the isolated host, give it to Algenta, and install the signed license file you receive.

{% stepper %}
{% step %}
### Get the device id of the air-gapped host

On the isolated host, read the stable device identifier the license is bound to. The raw machine id is hashed and never leaves the machine.

```bash
de license
```

`de license` prints the device id, plan, device limit, permitted modules, license source, and expiry. Send the device id to Algenta (across the air gap, e.g. on removable media) so your license can be issued for this exact machine.
{% endstep %}

{% step %}
### Install the license and the trust anchor on the air-gapped host

Algenta provides a signed license file (`license.jwt`) bound to that device id, and the matching **public key** that verifies it. Carry both across the air gap, place the token where the runtime loads it, and point the runtime at the public key. The default license path is `~/.algenta/runtime/license.jwt` (override the directory with `ALGENTA_RUNTIME_DIR`).

```bash
mkdir -p ~/.algenta/runtime
cp ./license.jwt ~/.algenta/runtime/license.jwt
chmod 600 ~/.algenta/runtime/license.jwt

# Trust anchor: the RS256 public key that verifies the license, fully offline.
export ALGENTA_LOCAL_LICENSE_PUBLIC_KEY_FILE=/etc/algenta/license_pub.pem

# Strict private profile: require a local signed license, no control-plane registration.
export ALGENTA_DEPLOYMENT_MODE=air_gapped
export ALGENTA_REQUIRE_LOCAL_LICENSE=1
```

The token may instead live in a platform secret via `ALGENTA_LICENSE_JWT` (or `ALGENTA_LICENSE_JWT_FILE`) so a redeployed container keeps a valid license without a persistent volume; the file on disk takes precedence when both are present. Verification is unchanged — RS256, fully offline.
{% endstep %}

{% step %}
### Verify the license offline

Confirm the runtime accepts the installed token without any network. `scripts/license_status.py` loads the token the same way the engine does at startup — no secrets, no network, no mutation.

```bash
python3 scripts/license_status.py
```
{% endstep %}
{% endstepper %}

{% hint style="success" %}
**Expected result** — `license_status.py` prints a line beginning with `OK` and exits `0`, for example:

```text
OK  license valid=True version=2 source=offline-local plan=enterprise
      deployment_class=airgapped commercial_use=True
      caps: seats=0 nodes=0 workers=0
      expiry: expires_at=1788220800 key_expires_at=1788220800 expired=False in_grace=False hard_expired=False
```

`source=offline-local` confirms the license was verified by your trust anchor (RS256) with no control-plane contact. `valid=True` and `version=2` mean the runtime would accept it. (Run `python3 scripts/license_status.py --json` for the machine-readable form.)
{% endhint %}

{% hint style="warning" %}
If the gate reports `FAIL` with `key_expires_at<=0`, the issued license has no key expiry. Request a license with a real key expiry (or, only for a deliberately no-expiry license, run `scripts/license_status.py --allow-no-key-expiry`).
{% endhint %}

## How the egress policy fails closed

In the `air_gapped` profile the runtime applies a private profile that sets `disable_cloud`, `disable_telemetry`, and **`allow_outbound_network=False`** by default. Every outbound attempt is classified into one of five classes and checked against the policy:

| Egress class | Air-gapped verdict |
| --- | --- |
| `algenta_cloud` | Denied — `algenta_cloud_disabled` |
| `vendor_telemetry` | Denied — `vendor_telemetry_disabled` |
| `customer_connector` / `operator_service` | Denied unless the host is in `ALGENTA_EGRESS_ALLOWLIST` |
| `undeclared_public` | Denied — `undeclared_public_egress_disabled` |

Nothing reaches the network unless you explicitly allowlist its host. The allowlist accepts exact hosts, `host:port`, and `*.suffix` wildcards — use it only for in-perimeter destinations such as an internal object store, never a public endpoint.

```bash
# Permit ONLY in-perimeter destinations; everything else stays denied.
export ALGENTA_EGRESS_ALLOWLIST="minio.internal:9000,*.db.example.internal"
```

Two further guardrails apply specifically to `air_gapped`:

* Setting `ALGENTA_TELEMETRY_MODE=control_plane_sync` or `ALGENTA_METERING_MODE=control_plane_sync` raises `air_gapped_control_plane_sync_forbidden` at startup — the mode cannot be tricked into syncing.
* With `ALGENTA_REQUIRE_LOCAL_LICENSE=1`, hosted registration is disabled: the runtime never attempts the API-key-for-license exchange, and a missing or unsigned license fails closed at load time rather than reaching out.

{% hint style="info" %}
`ALGENTA_DISABLE_TELEMETRY=1` (the private-profile default) means no outbound or vendor telemetry. It does **not** disable local audit — usage is still recorded on the host under `local_audit` for telemetry and metering, and a redacted, hashed audit record is produced for every egress decision. Observability stays self-hosted.
{% endhint %}

## Confirm there is no outbound traffic

You verify "no phone home" at two layers — the policy and the wire.

{% stepper %}
{% step %}
### Read back the effective policy

The engine's infrastructure surface reports the active deployment mode and engine state. Confirm the mode is `air_gapped` and the engine is local.

```bash
curl -sS http://localhost:8000/v1/infrastructure \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

Expect `engine_mode: binary`, a primary node with `status: live`, and a deployment profile that reflects the air-gapped, cloud-disabled configuration.
{% endstep %}

{% step %}
### Watch the wire

Because the policy fails closed, there should be **zero** outbound connections beyond any host you explicitly allowlisted. Observe the host's egress while you drive real requests through the API.

```bash
# Linux: watch for any non-loopback, non-allowlisted outbound connections.
ss -tup state established
```

The only established connections should be local deployment traffic and any host you placed in `ALGENTA_EGRESS_ALLOWLIST`. The strongest proof is operational: run the box on a network segment with no egress route and confirm requests still succeed.
{% endstep %}
{% endstepper %}

## Engine settings that matter offline

Two decisions shape how the engine behaves once it cannot reach anything.

**Compute policy — fail closed.** The production image requires its bundled compiled runtime. A missing or invalid artifact fails startup or compute explicitly; it does not route work to a hidden Python implementation. If the runtime directory is not writable, Algenta raises `repository_runtime_unwritable` rather than spilling tenant artifacts to ephemeral storage. Point `ALGENTA_RUNTIME_DIR` at a writable, durable, mounted path.

**LLM work — no LLM vs. BYOK.** The deterministic decision and simulation engine needs no model and runs fully offline. Only the agentic repository / GitHub flow needs an LLM, and air-gapped means you cannot use managed billing.

* **No LLM** — leave provider keys unset. Deterministic queries, decisions, and simulations work; the agentic flow that requires a model is simply unavailable.
* **BYOK (bring your own key)** — supply your organization's provider credentials for a model reachable inside the perimeter. Set a key in `.env` (encrypted at rest with `ALGENTA_CONFIG_ENCRYPTION_KEY`) and add the model host to `ALGENTA_EGRESS_ALLOWLIST` so the otherwise-denied connector call is permitted.

```bash
# BYOK against an in-perimeter, OpenAI-compatible model gateway.
ANTHROPIC_API_KEY=sk-ant-...
ALGENTA_CONFIG_ENCRYPTION_KEY="<64-hex-kek>"
ALGENTA_EGRESS_ALLOWLIST="llm-gateway.internal:443"
```

{% hint style="warning" %}
Managed LLM pass-through (where Algenta supplies the model key and meters spend) is off by default and depends on the control plane — it has no place in an air-gapped deployment. Use no LLM, or BYOK against a model inside your perimeter.
{% endhint %}

## Next steps

{% content-ref url="device-binding.md" %}
[device-binding.md](device-binding.md)
{% endcontent-ref %}

{% content-ref url="../engine/bundled-runtime.md" %}
[bundled-runtime.md](../engine/bundled-runtime.md)
{% endcontent-ref %}

{% content-ref url="../concepts/deployment-modes.md" %}
[deployment-modes.md](../concepts/deployment-modes.md)
{% endcontent-ref %}

{% content-ref url="../self-hosting.md" %}
[self-hosting.md](../self-hosting.md)
{% endcontent-ref %}
