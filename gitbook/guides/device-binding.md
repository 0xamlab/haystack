---
icon: fingerprint
description: Bind an Algenta offline license to a machine identity so it cannot be copied, print the device id, verify a bound license, and fix a device_identity_mismatch.
---

# Device binding

Device binding ties an Algenta license to a stable machine identity. The control plane (or an offline-signed license) records the identity of the machine it was issued for, and the local runtime checks that identity on every startup. A license file copied to a different host will not validate there, so one license stays on one machine even though it lives in a plain file on disk.

Binding works on two layers:

- **A privacy-preserving device id (fingerprint).** Derived locally from an OS-native machine id; only a one-way hash ever leaves the machine. This is what a device-capped API key counts and pins.
- **A per-device Ed25519 key (cryptographic binding).** Generated and stored on the machine; the private key never leaves it. The license records the public-key thumbprint, and renewal proves possession by signing a server nonce. A fingerprint can be cloned; a private key cannot.

{% hint style="info" %}
Binding is enforced only when there is something to enforce against: a device-capped API key (`device_limit > 0`), or an offline license that carries a `device_id` / `device_pubkey_thumbprint` claim. An uncapped key with no bound claims is not device-restricted. See [Licensing](../licensing.md).
{% endhint %}

## How the device id is derived

The runtime builds a stable, hashed device id locally. It reads the best-available OS-native machine id, then hashes it so the raw value never leaves the machine:

```text
device_id = SHA-256( raw_machine_id + ":algenta-device-v1" )[:32]   # hexdigest, first 32 chars
```

The raw machine id is read per platform, falling back gracefully:

| Platform | Raw source |
| --- | --- |
| macOS | `IOPlatformUUID` (from `ioreg`) |
| Linux | `/etc/machine-id` or `/var/lib/dbus/machine-id` |
| Windows | `HKLM\SOFTWARE\Microsoft\Cryptography\MachineGuid` |
| Fallback | a UUID generated once and persisted to `install_id` in the runtime dir |

The salt (`algenta-device-v1`) is a fixed, version-namespaced, non-secret constant baked into the runtime — it namespaces the hash, it is not a per-deployment secret. Because the device id is a hash of the salt plus the raw machine id, the same machine always produces the same id, and the raw id cannot be reversed out of it.

{% hint style="warning" %}
The device id is **derived**, not configured. There is no environment variable that changes the salt. What you can relocate is the runtime directory: `ALGENTA_RUNTIME_DIR` (default `~/.algenta/runtime`) determines where the fallback `install_id`, the encrypted device key, and the stored license live. On a host with no OS machine id (some containers), the id comes from that persisted `install_id` — so the **directory must persist** for the id to stay stable.
{% endhint %}

Alongside the id, the runtime sends non-sensitive context used for consistency checks: `platform`, `platform_version`, a `hostname_hash` (a truncated hash of the hostname, not the hostname itself), and the `sdk_version`.

## Print the device id

The device id is shown by the CLI. To register and bind this machine, run `de login`, which prints the id prefix before exchanging your API key for a license:

```bash
export ALGENTA_API_KEY="$ALGENTA_API_KEY"
de login
```

To inspect the current binding without re-registering, use the status command:

```bash
de license status
```

**Expected result.** `de license status` prints the bound device id (truncated for display), platform, plan, and license source, for example:

```text
Device ID:  3f9a1c2b...8e04  (Darwin)
Plan:       enterprise
Devices:    max 3
Modules:    all
Source:     cloud
Expires:    2027-05-19
```

A `Source:` of `cloud` (or `offline-local` for an air-gapped license) with a populated `Device ID:` confirms a bound, validated license. `dev-stub` means a self-signed local dev license, and `none` / a `Note:` line means no valid license is installed.

## How a bound license is verified

The license is a JWT stored at `~/.algenta/runtime/license.jwt` (or supplied via the `ALGENTA_LICENSE_JWT` / `ALGENTA_LICENSE_JWT_FILE` env for hosts without a persistent volume). On every startup the runtime verifies it **locally, with no network**:

{% stepper %}
{% step %}
**Signature.** Offline / cloud licenses are verified with RS256 against the Algenta public key (`ALGENTA_LICENSE_PUBLIC_KEY` or `ALGENTA_LICENSE_PUBLIC_KEY_FILE`). Self-signed dev tokens use HS256. A token without a v2 (`ver >= 2`) claim is rejected.
{% endstep %}
{% step %}
**Expiry and grace.** Expiry is checked against a persisted trusted clock that only moves forward. After `expires_at` the license enters a grace window (default 14 days) before a hard block.
{% endstep %}
{% step %}
**Identity.** The license carries the `device_id` it was issued for, and a v2 license can also carry a `device_pubkey_thumbprint`. On renewal the runtime proves possession of the bound private key by signing a server-issued nonce — the private key itself is never transmitted.
{% endstep %}
{% endstepper %}

For a device-capped API key, the control plane enforces binding at registration time: the first identity it sees for a `device_id` is recorded, and a later registration of the same id with **different** `hostname_hash` or `platform` is rejected.

## Fix a device_identity_mismatch

When a device-capped key re-registers a device id whose machine metadata no longer matches what was first bound, the API fails closed:

```json
{
  "error": {
    "code": "device_identity_mismatch",
    "message": "Device '<id>' is already bound to different identity metadata for this API key. Reuse the original device identity or register a different device ID.",
    "details": { "mismatched_fields": ["hostname_hash", "platform"] }
  }
}
```

It is a `403`. The `mismatched_fields` list tells you exactly which identity fields diverged. Common causes:

- **The machine moved or was reimaged**, changing the OS machine id (and therefore the hostname hash / platform behind a manually pinned device id).
- **A container or VM was rebuilt**, so an ephemeral host now presents fresh `platform` / `hostname_hash` values under a reused device id.
- **Hand-crafted requests** that send a pinned `X-Algenta-Device-Id` but drop or change `X-Algenta-Platform` / `X-Algenta-Hostname-Hash` (or omit the binding token the server issued on first bind).

Note that a genuinely new machine produces a **different** device id (different raw machine id), which counts as a new device — that path returns `402 device_limit_reached`, not a mismatch. The mismatch error specifically means "same id, different machine metadata."

To fix or rebind:

{% tabs %}
{% tab title="SDK / runtime (recommended)" %}
Let the SDK and runtime derive the identity for you instead of crafting headers. The SDK computes a stable device id and consistent `platform` / `hostname_hash`, and persists the binding token across calls:

```bash
export ALGENTA_API_KEY="$ALGENTA_API_KEY"
de login
```

If the machine legitimately changed, `de login` re-registers the current identity. If the key is at its device cap, an owner must first revoke the stale activation.
{% endtab %}
{% tab title="Pin a stable id (CI / containers)" %}
For ephemeral hosts, pin one stable device id per pool and send consistent metadata on every request, replaying the binding token the server returned on first bind:

```bash
export ALGENTA_DEVICE_ID="ci-runner-amd64-pool-01-stable"   # 16–64 chars; DE_DEVICE_ID also accepted
```

Keep `X-Algenta-Device-Id`, `X-Algenta-Platform`, and `X-Algenta-Hostname-Hash` identical across jobs and persist `ALGENTA_RUNTIME_DIR` so the fallback `install_id` survives. Without the original binding token, an already-bound id returns `401 device_binding_token_required`.
{% endtab %}
{% tab title="Offline license" %}
For air-gapped hosts, print the target machine's device id on that host with `de license` and send it to Algenta. Algenta returns an offline-signed license bound to that exact device id; load it locally:

```bash
cp ./license.jwt ~/.algenta/runtime/license.jwt
```

Copy the license to `~/.algenta/runtime/license.jwt` (or set `ALGENTA_LICENSE_JWT_FILE`). Set `ALGENTA_REQUIRE_LOCAL_LICENSE=1` to require a signed local license and disable any hosted registration. See [Run air-gapped](air-gapped.md).
{% endtab %}
{% endtabs %}

{% hint style="success" %}
After rebinding, run `de license status` again. A populated `Device ID:` with `Source: cloud` (or `offline-local`) and no `[HARD EXPIRED]` marker means the bound license validates on this machine.
{% endhint %}

## Manage your devices and seats

Each machine you register uses one **seat**, up to your plan's device limit. When you replace a laptop, rotate a server, or simply hit the limit, you free a seat by **revoking** a device you no longer use.

Manage your devices yourself from your **account dashboard**, no API key required — you sign in with your normal account. The dashboard lists every machine on your plan with its platform and when it was last active (marked **active** or **idle**), and a **Revoke** action next to each one:

- **See your seats.** The list shows how many of your devices are currently active versus idle, so you can tell at a glance which machine to retire.
- **Revoke to free a seat.** Revoking a device frees its seat immediately for a new machine. The revoked device loses access on its next license refresh.
- **Add the replacement.** Once a seat is free, run `de login` on the new machine (see [Fix a device_identity_mismatch](#fix-a-device_identity_mismatch) above) and it registers into the freed seat.

{% hint style="info" %}
Revoking is scoped to your own account: you only ever see and revoke devices on your own plan. A revoked device can re-register later if a seat is available — revoking frees the seat, it does not permanently ban the machine.
{% endhint %}

## Next steps

- [Licensing](../licensing.md) — plans, the license JWT, grace periods, and how binding fits the offline model.
- [Run air-gapped](air-gapped.md) — provision an offline-signed, device-bound license with no outbound network.
- [Self-hosting](../self-hosting.md) — run the runtime and control plane on your own infrastructure.
- [Troubleshooting](../troubleshooting.md) — `device_identity_mismatch`, `device_limit_reached`, and binding-token errors.
- [Glossary](../help/glossary.md) — definitions for device id, fingerprint, and entitlement.
