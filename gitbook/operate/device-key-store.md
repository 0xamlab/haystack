---
icon: key
description: Choose where Algenta stores the per-device private key — Apple Secure Enclave, a Linux TPM, the OS keyring, or an encrypted file — and confirm the runtime is healthy with runtime doctor.
---

# Choose a device key store backend

Every machine that runs the Algenta runtime holds a per-device signing key. It is the machine's cryptographic identity: the license records the key's public thumbprint, and renewal proves possession by signing a server nonce. The **private key never leaves the machine**. Where that private key is stored is selectable, so you can pin it to hardware on a laptop and to a deterministic encrypted file on a headless server.

You pick the store with a single runtime environment variable, `ALGENTA_DEVICE_KEY_STORE`, then restart the runtime and confirm it is healthy with `algenta runtime doctor`.

{% hint style="info" %}
These are **runtime-side** settings — environment variables set on the machine that runs the engine, not values sent over the API. Set them in that host's shell, `.env`, or orchestrator before the runtime starts. See [Configuration reference](../configuration.md).
{% endhint %}

## Choose a backend

`ALGENTA_DEVICE_KEY_STORE` accepts `auto` (the default), `secure_enclave`, `tpm`, `keyring`, or `file`. `auto` uses the OS keyring when a working keychain session is available and otherwise falls back to the encrypted file; the hardware backends (`secure_enclave` / `tpm`) are opt-in and never selected automatically, which keeps a device's identity stable. Force a value when you want a specific guarantee or a deterministic path for headless and CI hosts.

| Value | Where the private key lives | Best for |
| --- | --- | --- |
| `auto` (default) | OS keyring when available, otherwise the encrypted file | Any host — prefers the keyring, falls back to a file |
| `secure_enclave` | Apple Secure Enclave (macOS hardware) | macOS machines with a Secure Enclave |
| `tpm` | TPM 2.0 chip (Linux hardware) | Linux servers with a TPM |
| `keyring` | OS keychain (macOS Keychain, Linux Secret Service, Windows Credential Manager) | Desktops with a logged-in keychain session |
| `file` | Encrypted file in the runtime dir (`device_key.enc`, mode `0600`) | Headless servers, containers, CI — deterministic and hermetic |

{% hint style="info" %}
The encrypted-file store is bound to the machine: the file is encrypted with a key derived from the host's raw machine id, which is never transmitted. A key file copied to another machine will not decrypt there, so it is regenerated. The runtime directory defaults to `~/.algenta/runtime` and can be relocated with `ALGENTA_RUNTIME_DIR` — keep that directory persistent so the key survives restarts.
{% endhint %}

## Set the backend and verify

{% stepper %}
{% step %}
### Select a store on the engine host

Set `ALGENTA_DEVICE_KEY_STORE` (and, for the TPM path, its two companions) in the environment of the machine that runs the runtime.

{% tabs %}
{% tab title="macOS Secure Enclave" %}
```bash title="macOS: hardware-backed key"
export ALGENTA_DEVICE_KEY_STORE=secure_enclave
```

On macOS this stores the private key in the Apple Secure Enclave. The key material is generated in and never leaves the secure hardware; the runtime asks the enclave to sign renewal nonces.
{% endtab %}

{% tab title="Linux TPM" %}
```bash title="Linux: TPM 2.0-backed key"
export ALGENTA_DEVICE_KEY_STORE=tpm
export ALGENTA_TPM_ENABLE=1
export ALGENTA_TPM_TCTI="device:/dev/tpmrm0"
```

Requires a TPM 2.0 chip. `ALGENTA_TPM_ENABLE=1` turns the TPM path on and `ALGENTA_TPM_TCTI` selects the TPM Command Transmission Interface — set it to your host's TPM device (for example the in-kernel resource manager `device:/dev/tpmrm0`).
{% endtab %}

{% tab title="keyring" %}
```bash title="OS keychain"
export ALGENTA_DEVICE_KEY_STORE=keyring
```

Stores the key in the OS keychain — macOS Keychain, Linux Secret Service (GNOME Keyring / KWallet), or Windows Credential Manager. Requires the optional `keyring` package and a working backend session; a headless host with no keychain has none, so use `file` there instead.
{% endtab %}

{% tab title="file" %}
```bash title="Encrypted file (headless / CI)"
export ALGENTA_DEVICE_KEY_STORE=file
```

Writes an encrypted `device_key.enc` (mode `0600`) under the runtime directory. This is the deterministic, hermetic choice for servers, containers, and CI — no keychain session or hardware required.
{% endtab %}
{% endtabs %}
{% endstep %}

{% step %}
### Restart and confirm the runtime

Restart the runtime so it reads the new environment, then run the doctor. The runtime generates and persists the device key in the selected backend on first use, and the doctor confirms the runtime is loaded, verified, and licensed.

```bash title="algenta runtime doctor"
algenta runtime doctor
```

It reports the runtime source and mode, whether the native runtime is `loaded` and `verified`, the license state, and an overall `status`:

```text
algenta runtime doctor
  runtime source:  bundled sidecar
  mode:            resident-worker
  path:            /opt/algenta/runtime/algenta_runtime_worker
  platform tag:    manylinux_2_28_x86_64
  package version: 1.0.0
  abi (expected):  1
  abi (native):    1
  loaded:          True
  verified:        True
  fallback:        denied
  tcp listeners:   none
  license:         valid (tier=pro, exp=1788645600)
  status:          READY
```
{% endstep %}
{% endstepper %}

{% hint style="success" %}
**Expected result** — after restarting, `algenta runtime doctor` reports `loaded: True`, `verified: True`, and `status: READY`. On a hardware backend (`secure_enclave` / `tpm`) the device key is generated inside the secure element and never leaves it; on `file` the encrypted `device_key.enc` is written under the runtime directory.
{% endhint %}

{% hint style="warning" %}
Changing the store does not migrate an existing key — the runtime generates a fresh device key in the new backend on first use, which is a new device identity. If the machine is already bound to a device-capped key or an offline license, rebind it after switching (run `de login`, or reissue an offline license for the new thumbprint). See [Device binding](../guides/device-binding.md).
{% endhint %}

## Next steps

<table data-view="cards"><thead><tr><th></th><th></th><th data-hidden data-card-target data-type="content-ref"></th></tr></thead>
<tbody>
<tr><td><strong>Bind the license to this machine</strong></td><td>Register the device and verify a bound license.</td><td><a href="../guides/device-binding.md">../guides/device-binding.md</a></td></tr>
<tr><td><strong>Run fully air-gapped</strong></td><td>Provision an offline, device-bound license with no outbound network.</td><td><a href="../guides/air-gapped.md">../guides/air-gapped.md</a></td></tr>
<tr><td><strong>Tune the runtime environment</strong></td><td>Every variable the runtime reads, with defaults.</td><td><a href="../configuration.md">../configuration.md</a></td></tr>
</tbody></table>
