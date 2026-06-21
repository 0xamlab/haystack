---
icon: screwdriver-wrench
---

# Troubleshooting

This page collects the failure modes you are most likely to hit when running Algenta, and the exact fix for each. Every command, header, environment variable, and endpoint below is copied from the engine, SDKs, CLI, and MCP server as they actually ship. Find the symptom, run the diagnostic, apply the fix.

Start with the two fastest health checks. They isolate most problems in seconds.

```bash title="fast-health-checks.sh"
# Is the engine up and answering?
curl http://localhost:8000/v1/health

# Is the local license gate satisfied?
python3 scripts/license_status.py
```

{% hint style="success" %}
A healthy engine returns `{"status":"ok", ...}`. A satisfied license prints a line beginning with `OK` and exits `0`.
{% endhint %}

## Quick reference

| Symptom | Error code / signal | Jump to |
| --- | --- | --- |
| `403` on a capped key after changing machines or stripping headers | `device_identity_mismatch` | [Device identity mismatch](#device-identity-mismatch) |
| Engine refuses to start, or `license_status.py` prints `FAIL` | license gate not satisfied | [License gate failing](#license-gate-failing) |
| SDK still talks to the cloud, or refuses to start | base_url / cloud-disabled error | [Self-hosted mode does not fall back to cloud](#self-hosted-mode-does-not-fall-back-to-cloud) |
| `RuntimeError: Set ALGENTA_API_KEY or DE_API_KEY` | missing credential | [Missing API key](#missing-api-key) |
| Per-tenant provider keys decrypt to errors after a restart | encryption key lost | [Compose persistence](#compose-persistence-keep-your-env-stable) |
| MCP client shows no tools, or cannot connect | wrong base_url / key / transport mode | [MCP server not connecting](#mcp-server-not-connecting) |

## Device identity mismatch

On a device-capped API key, Algenta binds the first device identity it sees and then enforces it. The binding is keyed on the device id plus a small set of identity fields. If you reuse the same `X-Algenta-Device-Id` from a different machine, or send the id but drop the fingerprint headers, the request fails closed.

The server returns HTTP `403` with `code: "device_identity_mismatch"`:

```json title="403-device-identity-mismatch.json"
{
  "error": {
    "code": "device_identity_mismatch",
    "message": "Device '<device_id>' is already bound to different identity metadata for this API key. Reuse the original device identity or register a different device ID.",
    "details": {
      "device_id": "<device_id>",
      "plan": "<plan>",
      "mismatched_fields": ["hostname_hash", "platform"]
    }
  }
}
```

The fields that must stay consistent for a given device id are exactly:

| Header | Field |
| --- | --- |
| `X-Algenta-Device-Id` | device id (binds the activation) |
| `X-Algenta-Platform` | `platform` (consistency-checked) |
| `X-Algenta-Hostname-Hash` | `hostname_hash` (consistency-checked) |
| `X-Algenta-Platform-Version` | `platform_version` |
| `X-Algenta-Device-Binding-Token` | replay token issued on first bind |

{% hint style="info" %}
Use the Algenta SDK. It derives a stable per-machine device id, computes the platform and hostname-hash headers, and persists the binding token for you. The Python SDK builds these via `decision_engine.device_headers.build_device_headers` and stores the binding token through `store_device_binding_token` / `load_device_binding_token`. You only hit `device_identity_mismatch` when you craft headers by hand.
{% endhint %}

### Fix

{% stepper %}
{% step %}
### Send a consistent identity from each machine
The same device must always present the same `X-Algenta-Device-Id`, `X-Algenta-Platform`, and `X-Algenta-Hostname-Hash`.
{% endstep %}

{% step %}
### Replay the binding token
After the first successful registration, capture the value the server issued and send it back on every subsequent call as `X-Algenta-Device-Binding-Token`. Without it, an already-bound device id is rejected with `device_binding_token_required` (HTTP `401`).
{% endstep %}

{% step %}
### If you genuinely changed machines, do not reuse the old id
Pick a new device id (the SDK does this automatically) or have an owner revoke the old activation.
{% endstep %}
{% endstepper %}

To pin a deterministic id explicitly, set one of these before starting your client. It must be 16 to 64 characters:

```bash title="pin-device-id.sh"
export ALGENTA_DEVICE_ID="ci-runner-amd64-pool-01-stable"
# legacy alias also accepted:
export DE_DEVICE_ID="ci-runner-amd64-pool-01-stable"
```

{% expandable title="Advanced: a raw request that mirrors what the SDK sends" %}
```bash title="device-headers-by-hand.sh"
curl -X POST "$ALGENTA_BASE_URL/v1/simulate" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -H "X-Algenta-Device-Id: ci-runner-amd64-pool-01-stable" \
  -H "X-Algenta-Platform: Linux" \
  -H "X-Algenta-Platform-Version: 6.8.0" \
  -H "X-Algenta-Hostname-Hash: 3f5c...e21a" \
  -H "X-Algenta-Device-Binding-Token: $ALGENTA_DEVICE_BINDING_TOKEN" \
  -d '{ "mode": "auto", "scenario": { "variables": { "revenue": { "low": 80000, "high": 200000 } }, "objective": "maximize_net_value" }, "runs": 1000, "seed": 42 }'
```
{% endexpandable %}

{% hint style="warning" %}
In CI, every job must carry the same device id and the same fingerprint headers, or the first job binds and the rest fail closed. Set `ALGENTA_DEVICE_ID` once for the pool and persist the binding token so it can be replayed across jobs.
{% endhint %}

## License gate failing

Self-hosted deployments validate a local license. When the gate is not satisfied the engine fails closed under enforcement. The authoritative diagnostic is `scripts/license_status.py`, which loads the installed token through the same code path the runtime uses. No network, no mutation.

{% tabs %}
{% tab title="Human-readable" %}
```bash
python3 scripts/license_status.py
```

A satisfied gate prints a line like this and exits `0`:

```
OK  license valid=True version=2 source=offline-local plan=enterprise
```
{% endtab %}

{% tab title="JSON" %}
```bash
python3 scripts/license_status.py --json
```

Exit `0` means the gate is satisfied. Exit `1` means it is not (invalid, expired, or `v1` where `v2` is required).
{% endtab %}
{% endtabs %}

### Common causes and fixes

| Cause | What you see | Fix |
| --- | --- | --- |
| Invalid or expired token | `FAIL  license valid=False ...` | Reissue and reinstall a valid token |
| A `v1` token where `v2` is required | `FAIL ... version=1` | Issue a `v2` token, or pass `--allow-v1` only if your deployment runs the v1-tolerant path |
| `key_expires_at <= 0` | `FAIL` even though the token verifies | Issue with a real `--key-expires-at`, or accept no-expiry with `--allow-no-key-expiry` |
| Public key not installed | `FAIL  could not load license: ...` | Install `ALGENTA_LOCAL_LICENSE_PUBLIC_KEY` (or the `_FILE` variant) |

{% hint style="warning" %}
The `key_expires_at <= 0` case is subtle. `scripts/issue_offline_license.py` defaults `key_expires_at` to `0`, which verifies fine under the `require_local_license` path but is rejected by the stored-entitlement enforcement sub-path. `license_status.py` fails the gate conservatively so it never green-lights a machine the runtime would then deny.
{% endhint %}

Issue a token with a real key expiry:

```bash title="issue-with-expiry.sh"
python3 scripts/issue_offline_license.py --key-expires-at 1782950400  # unix seconds
```

Or, for a deliberate no-expiry license that will only ever run under the `require_local_license` path, accept it explicitly:

```bash title="accept-no-expiry.sh"
python3 scripts/license_status.py --allow-no-key-expiry
```

### Install the verification public key

`license_status.py` and the runtime verify the token signature against the public key you provide. Install it inline or from a file:

{% tabs %}
{% tab title="Inline PEM" %}
```bash
export ALGENTA_LOCAL_LICENSE_PUBLIC_KEY="$(cat algenta_license_pub.pem)"
```
{% endtab %}

{% tab title="By path" %}
```bash
export ALGENTA_LOCAL_LICENSE_PUBLIC_KEY_FILE="/etc/algenta/license_pub.pem"
```
{% endtab %}
{% endtabs %}

{% expandable title="Advanced: key and token resolution order" %}
The runtime reads `ALGENTA_LOCAL_LICENSE_PUBLIC_KEY` then `ALGENTA_LICENSE_PUBLIC_KEY` (and the `_FILE` variants). The installed token is read from `~/.algenta/runtime/license.jwt` by default.
{% endexpandable %}

{% hint style="info" %}
Run `python3 scripts/license_status.py` on every machine before flipping a deployment to enforce. Confirm it prints `OK` and exits `0` first.
{% endhint %}

## Self-hosted mode does not fall back to cloud

`self_hosted` and `air_gapped` profiles never silently call the Algenta cloud. The SDK clients expose the Cloud Managed path by default; for private deployments you must pass an explicit self-hosted `base_url` and the API key provisioned by your own control plane.

If cloud is disabled and you do not supply a base_url, the SDK raises rather than defaulting to an Algenta-owned host:

```
Cloud is disabled but the resolved base_url points at an Algenta-owned host.
Configure a self-hosted base_url or ALGENTA_BASE_URL / DE_BASE_URL / ALGENTA_API_URL.
```

### Fix

Set the base_url explicitly. The SDK and CLI resolve it from the first of `ALGENTA_BASE_URL`, `DE_BASE_URL`, `ALGENTA_API_URL`:

{% tabs %}
{% tab title="Environment" %}
```bash title="self-hosted.env"
export ALGENTA_BASE_URL="http://localhost:8000"
export ALGENTA_API_KEY="<your self-hosted key>"
export ALGENTA_DISABLE_CLOUD=1
```
{% endtab %}

{% tab title="Python" %}
```python title="self_hosted_client.py"
import os
from decision_engine import Client

client = Client(
    base_url=os.environ["ALGENTA_BASE_URL"],   # explicit; no cloud fallback
    api_key=os.environ["ALGENTA_API_KEY"],
)
```
{% endtab %}

{% tab title="TypeScript" %}
```typescript title="self-hosted-client.ts"
import { Client } from "@algenta/sdk";

const client = new Client({
  baseUrl: process.env.ALGENTA_BASE_URL!,   // explicit; required when cloud is disabled
  apiKey: process.env.ALGENTA_API_KEY!,
});
```
{% endtab %}
{% endtabs %}

{% hint style="warning" %}
A self-hosted base_url must be an absolute URL including scheme and host (for example `http://localhost:8000`, not `localhost:8000`). A bare host raises `base_url must be an absolute URL including scheme and host.`
{% endhint %}

## Missing API key

The SDK examples read the key from the environment and raise immediately if it is absent. They accept `ALGENTA_API_KEY` with `DE_API_KEY` as a legacy alias:

```python title="require_key.py"
import os

ALGENTA_KEY = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
if not ALGENTA_KEY:
    raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")
```

### Fix

Export one of the accepted variables before running:

```bash title="export-key.sh"
export ALGENTA_API_KEY="<your key>"
# legacy alias, still accepted:
export DE_API_KEY="<your key>"
```

For the CLI, you can persist it instead of exporting each session:

```bash title="persist-key.sh"
de config set-key <YOUR_ALGENTA_API_KEY>
```

## Health and contract checks

When something behaves unexpectedly, confirm the engine is up and that your client and the engine agree on the contract.

{% tabs %}
{% tab title="cURL" %}
```bash
# Liveness — returns {"status":"ok","timestamp": "..."}
curl http://localhost:8000/v1/health

# Machine-readable platform contract (SDK/CLI/MCP surface)
curl http://localhost:8000/v1/meta/contract
```
{% endtab %}

{% tab title="CLI" %}
The CLI wraps both. The binary is `de`:

```bash
de health      # prints "API Status: OK"
de contract    # prints the resolved Algenta contract (add --json for raw)
```
{% endtab %}
{% endtabs %}

{% hint style="info" %}
`de contract` calls `GET /v1/meta/contract`. If that endpoint returns `404` (older engine), the CLI falls back to building the contract from `GET /openapi.json` automatically. A `404` on `/v1/meta/contract` alone is therefore not a failure.
{% endhint %}

## Compose persistence: keep your .env stable

Per-tenant provider keys are encrypted at rest with `ALGENTA_CONFIG_ENCRYPTION_KEY`. Encryption is opt-in: it is on only when that variable is set. If you set it, store a tenant key, then restart the stack with the variable missing or changed, the engine cannot decrypt the stored secret and surfaces errors such as:

```
secret is encrypted but ALGENTA_CONFIG_ENCRYPTION_KEY is not set
```

Setting a per-tenant key also refuses to store a plaintext value when the key is absent:

```
per-tenant keys require ALGENTA_CONFIG_ENCRYPTION_KEY (refusing to store a plaintext key)
```

### Fix

Treat `ALGENTA_CONFIG_ENCRYPTION_KEY` as durable secret material. Put it in your Compose `.env` and never rotate it without re-encrypting existing rows.

```bash title="infra/docker/.env"
# keep stable across restarts
ALGENTA_CONFIG_ENCRYPTION_KEY=<64-hex characters, generated once>
```

{% hint style="danger" %}
Losing or changing `ALGENTA_CONFIG_ENCRYPTION_KEY` breaks every per-tenant provider key already stored. There is no recovery without the original key. Back it up alongside your database, not inside it.
{% endhint %}

## MCP server not connecting

The Algenta MCP server runs in two transports: `stdio` (the default, for Claude Desktop, Cursor, Zed, Windsurf, VS Code Cline/Continue) and `http` (SSE, for OpenWebUI, LibreChat, n8n, custom apps). When a client shows no tools, the cause is almost always a missing credential, a missing base_url, or the wrong transport.

```bash title="start-mcp-server.sh"
# stdio (default)
python -m apps.mcp_server.server

# HTTP/SSE on port 8001
python -m apps.mcp_server.server --mode http

# HTTP/SSE on a custom port
python -m apps.mcp_server.server --mode http --port 9000
```

The server reads the same environment as the SDK:

| Variable | Purpose | Notes |
| --- | --- | --- |
| `ALGENTA_API_KEY` | required credential | `DE_API_KEY` accepted for compatibility |
| `ALGENTA_BASE_URL` | engine URL | `DE_BASE_URL` / `ALGENTA_API_URL` accepted; defaults to the cloud in Cloud Managed |

### Fix

{% stepper %}
{% step %}
### Confirm both variables are set
They must be set in the environment the MCP client launches the server in. For stdio, that is the client's config, not your shell.

```bash
export ALGENTA_API_KEY="<your key>"
export ALGENTA_BASE_URL="http://localhost:8000"
```
{% endstep %}

{% step %}
### Match the transport to the client
Desktop AI apps (Claude Desktop, Cursor) speak `stdio`; do not point them at `--mode http`. Web apps that expect SSE need `--mode http`.
{% endstep %}

{% step %}
### Verify the engine the server points at is healthy first
```bash
curl "$ALGENTA_BASE_URL/v1/health"
```
{% endstep %}
{% endstepper %}

{% hint style="warning" %}
A `stdio` client passes environment through its own config block. For self-hosted, ensure both `ALGENTA_API_KEY` and `ALGENTA_BASE_URL` appear there, or the server starts but resolves to the cloud default and authenticates against the wrong host.
{% endhint %}

## Verify a fresh install end to end

When you want a single command that proves the whole self-hosted stack works, run the smoke script. It builds the images, starts the Compose stack, runs migrations, bootstraps an owner and API key, rotates and revokes keys, and executes both a synchronous and an asynchronous decision.

```bash title="self_host_smoke.sh"
scripts/self_host_smoke.sh
```

A passing run ends with:

```
==> Self-hosted smoke passed
API=http://localhost:18000
API_KEY=...
```

{% hint style="info" %}
It exercises the real endpoints you will use in production, including `GET /v1/health`, `POST /v1/api-keys`, `POST /v1/simulate`, and the async `POST /v1/jobs` lifecycle. If the smoke passes but your own client fails, the difference is almost always credentials, base_url, or transport. Re-check those three first.
{% endhint %}

## Related pages

{% content-ref url="self-hosting.md" %}
[self-hosting.md](self-hosting.md)
{% endcontent-ref %}

{% content-ref url="authentication.md" %}
[authentication.md](authentication.md)
{% endcontent-ref %}

{% content-ref url="licensing.md" %}
[licensing.md](licensing.md)
{% endcontent-ref %}

{% content-ref url="sdk/mcp.md" %}
[sdk/mcp.md](sdk/mcp.md)
{% endcontent-ref %}
