---
icon: life-ring
description: Hit a snag? Find your message, copy the fix, get back to work — most Algenta issues are a missing key, an engine it can't reach, or a license flag.
---

# Troubleshooting

Hit a snag? Don't worry — almost every Algenta issue is one of three things: a **missing API key**, an **engine it can't reach**, or a **license the runtime is asking for**. Find your symptom below and you'll be unblocked in under a minute.

{% hint style="info" %}
In a hurry? The **Quick fixes** table is the 10-second answer for each message. Expand a card under it for the *why*, the exact command, and how to confirm it worked.
{% endhint %}

## Two fast health checks

Run these first — they isolate most problems in seconds.

```bash title="fast-health-checks.sh"
curl http://localhost:8000/v1/health      # is the engine up?
python3 scripts/license_status.py         # is the local license gate satisfied?
```

{% hint style="success" %}
A healthy engine returns `{"status":"ok", ...}`. A satisfied license prints a line beginning with `OK` and exits `0`.
{% endhint %}

## Quick fixes

| What you saw | The fix |
|---|---|
| `RuntimeError: Set ALGENTA_API_KEY or DE_API_KEY` | `export ALGENTA_API_KEY=…` |
| a connection error, or the call just hangs | point `ALGENTA_BASE_URL` at a running engine |
| `Cloud is disabled but the resolved base_url …` | set an explicit self-hosted `ALGENTA_BASE_URL` |
| `base_url must be an absolute URL …` | include the scheme: `http://localhost:8000` |
| `license_status.py` prints `FAIL` | reissue/reinstall a valid license + public key |
| `403 device_identity_mismatch` | send the same device headers, or use the SDK |
| `secret is encrypted but ALGENTA_CONFIG_ENCRYPTION_KEY is not set` | restore the original encryption key |
| your editor shows no Algenta tools | set the key + base_url in its MCP config, then restart |

## Getting connected

<details>

<summary>"Set ALGENTA_API_KEY or DE_API_KEY" — no key in this shell</summary>

The SDK reads your key from the environment and stops immediately if it's absent.

```bash title="export-key.sh"
export ALGENTA_API_KEY="$ALGENTA_API_KEY"   # DE_API_KEY is accepted as a legacy alias
```

For the CLI you can persist it instead of exporting each session with `de config set-key $ALGENTA_API_KEY`. You'll know it worked when your call runs instead of raising. Full key precedence is on **Authentication**.

</details>

<details>

<summary>A connection error, or the command just hangs</summary>

`ALGENTA_BASE_URL` isn't pointing at a running engine.

```bash title="check-engine.sh"
echo "$ALGENTA_BASE_URL"                 # default: http://localhost:8000
curl http://localhost:8000/v1/health     # expect {"status":"ok", ...}
```

A `200` with `status: ok` means the API is reachable. Anything else means the integrated deployment is unhealthy or the base URL is wrong; verify the self-hosted stack or point the client at the hosted URL, then retry.

</details>

<details>

<summary>"Cloud is disabled but the resolved base_url points at an Algenta-owned host"</summary>

The `self_hosted` and `air_gapped` profiles never silently call the Algenta cloud — so a private deployment must pass an explicit `base_url`.

```bash title="self-hosted.env"
export ALGENTA_BASE_URL="http://localhost:8000"   # absolute URL: scheme + host
export ALGENTA_API_KEY="$ALGENTA_API_KEY"
export ALGENTA_DISABLE_CLOUD=1
```

The SDK and CLI resolve the URL from the first of `ALGENTA_BASE_URL`, `DE_BASE_URL`, `ALGENTA_API_URL`. A bare host (`localhost:8000`) raises `base_url must be an absolute URL including scheme and host.` — include the `http://`.

</details>

## Licensing

<details>

<summary>"license_status.py prints FAIL" — the local gate isn't satisfied</summary>

Self-hosted deployments validate a local license and fail closed when the license is missing or invalid. `scripts/license_status.py` loads the token through the exact runtime path — no network, no mutation.

```bash title="license-status.sh"
python3 scripts/license_status.py          # OK + exit 0 = satisfied
python3 scripts/license_status.py --json   # machine-readable
```

The bottom line of the output names the next action. Most failures are an invalid/expired token (reissue), a missing public key (next card), or `key_expires_at <= 0` (the card after).

</details>

<details>

<summary>"could not load license" — the verification public key isn't installed</summary>

The runtime verifies the token signature against the public key you provide, inline or by path.

```bash title="install-public-key.sh"
export ALGENTA_LOCAL_LICENSE_PUBLIC_KEY="$(cat algenta_license_pub.pem)"
# or by path:
export ALGENTA_LOCAL_LICENSE_PUBLIC_KEY_FILE="/etc/algenta/license_pub.pem"
```

The runtime reads `ALGENTA_LOCAL_LICENSE_PUBLIC_KEY` then `ALGENTA_LICENSE_PUBLIC_KEY` (and the `_FILE` variants); the token comes from `~/.algenta/runtime/license.jwt` by default. Re-run `license_status.py` — it should now print `OK`.

</details>

<details>

<summary>"FAIL" even though the token verifies — key_expires_at ≤ 0</summary>

A license with no key expiry can fail the gate. Use a license that has a real key expiry, or pass `--allow-no-key-expiry` if a no-expiry license is intended.

```bash title="fix-key-expiry.sh"
# obtain a reissued license with a real key expiry from whoever provisions your license, then verify:
python3 scripts/license_status.py
# or accept a deliberate no-expiry license:
python3 scripts/license_status.py --allow-no-key-expiry
```

Full issuance is on **Licensing**.

</details>

## Self-hosted secrets

<details>

<summary>"secret is encrypted but ALGENTA_CONFIG_ENCRYPTION_KEY is not set"</summary>

Per-tenant provider keys are encrypted at rest with `ALGENTA_CONFIG_ENCRYPTION_KEY`. If you set it, store a key, then restart with the variable missing or changed, the engine can't decrypt — and it refuses to store a plaintext key without it (`per-tenant keys require ALGENTA_CONFIG_ENCRYPTION_KEY`).

```bash title="infra/docker/.env"
# keep this stable across restarts — generated once
ALGENTA_CONFIG_ENCRYPTION_KEY="<64-hex characters, generated once>"
```

Treat it as durable secret material: keep it in your Compose `.env`, back it up alongside (not inside) your database, and never rotate it without re-encrypting existing rows.

{% hint style="danger" %}
Losing or changing this key breaks **every** per-tenant provider key already stored. There is no recovery without the original.
{% endhint %}

</details>

## Device-bound keys

<details>

<summary>"403 device_identity_mismatch" — a capped key sees a new identity</summary>

On a device-capped API key, Algenta binds the first device identity it sees and enforces it. Reusing the same `X-Algenta-Device-Id` from a different machine — or sending the id but dropping the fingerprint headers — fails closed.

```bash title="pin-device-id.sh"
export ALGENTA_DEVICE_ID="ci-runner-amd64-pool-01-stable"   # 16–64 chars; DE_DEVICE_ID also accepted
```

Send a consistent `X-Algenta-Device-Id`, `X-Algenta-Platform`, and `X-Algenta-Hostname-Hash` from each machine, and replay the `X-Algenta-Device-Binding-Token` the server issued on first bind (without it, an already-bound id returns `401 device_binding_token_required`). Genuinely changed machines need a new id, or an owner revokes the old activation.

{% hint style="info" %}
Easiest fix: use the Algenta SDK — it derives a stable device id, computes the fingerprint headers, and persists the binding token for you. You only hit this when crafting headers by hand. In CI, set `ALGENTA_DEVICE_ID` once per pool and persist the token across jobs.
{% endhint %}

</details>

## In your editor (MCP)

<details>

<summary>Cursor, Claude Desktop, or another client shows no Algenta tools</summary>

Almost always a missing credential, a missing base_url, or the wrong transport. The server runs `stdio` by default (desktop AI apps) and `http`/SSE for web clients.

```bash title="start-mcp-server.sh"
python -m apps.mcp_server.server                 # stdio (Claude Desktop, Cursor, Zed, …)
python -m apps.mcp_server.server --mode http     # Streamable HTTP (OpenWebUI, LibreChat, n8n)
```

For `stdio`, the key and base_url must live in the **client's** config block, not your shell — set both `ALGENTA_API_KEY` and `ALGENTA_BASE_URL` there, then restart the client. Don't point a desktop app at `--mode http`. Verify the engine first with `curl "$ALGENTA_BASE_URL/v1/health"`. The exact config is on **MCP / IDE**.

</details>

## Still stuck?

That's on us to help. First capture the two diagnostics so we can see what you see:

```bash title="collect-diagnostics.sh"
curl -s http://localhost:8000/v1/health
python3 scripts/license_status.py --json
```

Then reach us from [algenta.ai](https://algenta.ai) with the exact error, the command you ran, and that output — and we'll get you unblocked.

{% hint style="info" %}
Want proof the whole self-hosted stack works end to end? `scripts/self_host_smoke.sh` builds the stack, bootstraps a key, and runs a real synchronous and asynchronous decision — ending in `==> Self-hosted smoke passed`. If the smoke passes but your own client fails, the difference is almost always credentials, base_url, or transport.
{% endhint %}

## Next

<table data-view="cards">
<thead><tr><th></th><th></th><th data-hidden data-card-target data-type="content-ref"></th></tr></thead>
<tbody>
<tr><td><strong>Authentication &#x26; keys</strong></td><td>Mint, scope, and rotate keys; device binding.</td><td><a href="authentication.md">authentication.md</a></td></tr>
<tr><td><strong>Self-hosting</strong></td><td>Run and operate the engine on your own infrastructure.</td><td><a href="self-hosting.md">self-hosting.md</a></td></tr>
<tr><td><strong>Licensing</strong></td><td>Issue, install, and verify an offline license.</td><td><a href="licensing.md">licensing.md</a></td></tr>
<tr><td><strong>MCP / IDE</strong></td><td>Connect Cursor, Claude Desktop, and web clients.</td><td><a href="sdk/mcp.md">sdk/mcp.md</a></td></tr>
</tbody>
</table>
