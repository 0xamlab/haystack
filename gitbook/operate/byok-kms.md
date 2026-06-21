---
icon: lock
description: Encrypt Algenta secrets at rest with your own AES-256-GCM key supplied through ALGENTA_CONFIG_ENCRYPTION_KEY.
---

# Encrypt secrets at rest with your own key

Algenta can encrypt the secrets it stores at rest using a symmetric key that you supply. You hold the key, you control where it lives, and you decide when encryption is enabled. There is no third-party key escrow and no phone-home: the engine reads one key from its environment at boot and uses it locally.

This guide covers what gets encrypted, how to generate and set the key, how to confirm encryption is on, and the operational care the key demands. It is most relevant to self-hosted deployments, where you own the process environment. See [../self-hosting.md](../self-hosting.md) for the broader deployment context.

## What this protects

When encryption is enabled, Algenta encrypts these secret-bearing values before they are written to the database:

- **Per-tenant provider and engine keys (BYOK).** The customer-supplied LLM/provider credentials and the per-org engine key. See [../guides/byok.md](../guides/byok.md).
- **Connector `config_json`.** Data-connector configuration, which can hold DSNs, passwords, and tokens.
- **Capability-binding configs.** The `config_json` stored on capability bindings.

The cipher is **AES-256-GCM** with a fresh random 12-byte IV per value. Each ciphertext is authenticated with additional authenticated data (AAD) bound to the owning `org_id` (and, for context-scoped secrets such as provider keys, a context label as well). That binding means a ciphertext cannot be decrypted under a different org or replayed into a different context — it is cryptographically pinned to where it was written.

{% hint style="info" %}
Encrypted values are stored with an `enc:v1:` prefix. On read, Algenta detects that prefix: prefixed values are decrypted, and any legacy plaintext value (no prefix) is returned unchanged. This is what makes enabling encryption a non-breaking, staged rollout.
{% endhint %}

## How encryption is gated

Encryption is **opt-in** and controlled entirely by one environment variable:

- **`ALGENTA_CONFIG_ENCRYPTION_KEY` unset** — values are written as plaintext and read back as-is. Existing rows are untouched. This is the default and supports a staged rollout.
- **`ALGENTA_CONFIG_ENCRYPTION_KEY` set** — new writes are encrypted with AES-256-GCM. Existing plaintext rows keep working (read-through), so you can enable the key first and re-encrypt later.

{% hint style="warning" %}
Per-tenant provider/engine keys are stricter than connector configs. Setting or rotating a tenant key **requires** the encryption key to be configured — the write is refused (HTTP `409`, code `encryption_key_required`) rather than storing a plaintext key. Connector and capability configs, by contrast, allow the plaintext-passthrough rollout described above.
{% endhint %}

## Generate and set the key

The key value can be either a 64-character hex string (interpreted as 32 raw bytes) or any passphrase (hashed to 32 bytes with SHA-256). A random 32-byte hex value is the recommended form.

{% stepper %}
{% step %}
### Generate a 32-byte key

```bash
openssl rand -hex 32
```

This prints a 64-character hex string. Treat the output as a secret.
{% endstep %}

{% step %}
### Supply it to the engine at boot

Set it in the engine's environment before the process starts. For example:

```bash
export ALGENTA_CONFIG_ENCRYPTION_KEY="$(openssl rand -hex 32)"
```

In a container or orchestrator, inject it as an environment variable through your normal secret-delivery mechanism. See [../configuration.md](../configuration.md) for how Algenta reads configuration.

**Expected result:** the variable is present in the engine process environment at startup. The key is read once at boot; it is never written to the database or transmitted off-host.
{% endstep %}

{% step %}
### Restart and confirm

Restart the engine so it picks up the new environment, then confirm encryption is active using the check below.
{% endstep %}
{% endstepper %}

## Confirm encryption is enabled

Encryption is on whenever `ALGENTA_CONFIG_ENCRYPTION_KEY` is set in the engine's environment, and off when it is unset. There is no separate switch to flip — the presence of the key is the state. The most reliable confirmation is the engine's own observable behavior rather than a config readout.

The clearest behavioral signal is a per-tenant key write. While `ALGENTA_CONFIG_ENCRYPTION_KEY` is unset, attempting to set a tenant provider or engine key returns HTTP `409` with the code `encryption_key_required` — the engine refuses to store the key as plaintext. Once the key is configured and the engine is restarted, that same request succeeds:

```bash
curl -sS -o /dev/null -w "%{http_code}\n" \
  -X PUT https://api.algenta.ai/v1/provider-keys/openai \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"api_key": "sk-example"}'
```

**Expected result:** `409` (body code `encryption_key_required`) when the variable is unset, and `200` once it is configured. From that point, newly written provider keys, connector configs, and capability-binding configs are stored with the `enc:v1:` ciphertext prefix in the database. See [../guides/byok.md](../guides/byok.md) for the key-management API.

## Key rotation — handle with care

{% hint style="danger" %}
The supplied key is used **directly** to decrypt existing ciphertext. There is no key-versioning or automatic re-wrap. If you change `ALGENTA_CONFIG_ENCRYPTION_KEY` without first re-encrypting stored values under the new key, every value encrypted under the old key becomes permanently undecryptable, and reads of those values will fail.
{% endhint %}

Operational guidance:

- **Back up the key.** Losing it means losing access to every value it encrypted. Store it where you can recover it (your secrets manager / KMS / vault).
- **Do not rotate in place.** Rotating means: decrypt all existing values under the old key, then re-encrypt under the new key, before the old key is removed from the environment. Plan rotation as a deliberate migration, not an environment-variable swap.
- **Keep it consistent across replicas.** Every engine and worker replica that reads or writes these values must run with the same key value, or one replica will be unable to decrypt what another wrote.

## External KMS or Vault

{% hint style="info" %}
Algenta has **no built-in external KMS or Vault integration**. It reads exactly one symmetric key from `ALGENTA_CONFIG_ENCRYPTION_KEY` and uses it locally.
{% endhint %}

You can still keep the key in an external KMS, HashiCorp Vault, or any secrets manager — the integration point is the environment. Have your platform fetch the key from that system and inject it into `ALGENTA_CONFIG_ENCRYPTION_KEY` at boot (for example, a startup wrapper that reads the secret and exports the variable before launching the engine). Algenta itself does not call out to a KMS, does not perform per-request key fetches, and has no KMS provider configuration.

## Next steps

- [Bring your own keys (BYOK)](../guides/byok.md)
- [Self-hosting Algenta](../self-hosting.md)
- [Configuration reference](../configuration.md)
- [Deployment modes](../concepts/deployment-modes.md)
