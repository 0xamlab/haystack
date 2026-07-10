---
icon: right-to-bracket
description: Sign in to Algenta from the terminal with the browser-based device login — approve a short code at accounts.thyn.ai and the CLI stores a machine-scoped key for you.
---

# Log in from the terminal

`algenta login` signs this machine in to Algenta without you ever pasting a secret. The CLI shows a short code, you approve it once in your browser at **accounts.thyn.ai**, and the CLI exchanges that approval for a machine-scoped API key, registers the device, and stores the credential locally. Every later `algenta` command — and any tool that reads `ALGENTA_API_KEY` — then authenticates automatically.

This is the interactive, no-copy-paste path. If you already have an API key (for example one your self-hosted operator provisioned), you do not need to log in at all — set `ALGENTA_API_KEY` and go. See [Authentication & API keys](authentication.md).

{% hint style="info" %}
The bundled `algenta` CLI is rolling out and is not a public PyPI install yet. **API-key authentication works today** on every live surface — the SDKs, the `de` CLI, and raw HTTP all accept `Authorization: Bearer $ALGENTA_API_KEY` right now. See [Authentication & API keys](authentication.md) to mint and use a key while `algenta login` ships.
{% endhint %}

## Before you start

- An Algenta account on the hosted control plane (the browser step signs you in at `accounts.thyn.ai`).
- The `algenta` command on your PATH from a source checkout or a future published runtime release:

```bash title="install-algenta.sh"
git clone https://github.com/thyn-ai/algenta.git
cd algenta
python3 -m pip install -e packages/algenta
algenta version
```

{% hint style="warning" %}
Device login targets the hosted control plane. On a **self-hosted** or **air-gapped** deployment there is no browser sign-in — your operator provisions the API key directly. Skip this page and follow [Authentication & API keys](authentication.md) instead. Private profiles fail closed and never fall back to the Algenta cloud.
{% endhint %}

## Sign in

{% stepper %}
{% step %}
### Start the login

Run `algenta login`. The CLI requests a device code, prints a short **user code** (formatted `XXXX-XXXX`), and opens `accounts.thyn.ai/device` in your default browser.

```bash title="algenta-login.sh"
algenta login
```

On a headless box or over SSH, add `--no-browser`: the CLI prints the verification URL and the code instead of trying to launch a browser, so you can approve it from another machine.

```bash title="algenta-login-headless.sh"
algenta login --no-browser
```

The code expires after 10 minutes. If it lapses before you approve it, just run the command again for a fresh one.
{% endstep %}

{% step %}
### Approve the code in your browser

At `accounts.thyn.ai/device`, sign in if you are not already, confirm the code shown matches the one the CLI printed, and approve the request. The page tells you which client and scope you are authorizing before you confirm.

Meanwhile the CLI polls in the background and waits for your approval — leave it running.
{% endstep %}

{% step %}
### Let the CLI finish

Once you approve, the CLI receives the session, mints a machine-scoped API key for this device, registers the device, and stores the credential securely on your machine (the OS keyring when available, otherwise an encrypted file in the CLI's config directory). You do not see or handle the raw key.
{% endstep %}

{% step %}
### Confirm you are signed in

Confirm the machine is signed in:

```bash title="algenta-whoami.sh"
algenta whoami
```

It confirms this machine is signed in and prints the stored key's prefix.
{% endstep %}
{% endstepper %}

{% hint style="success" %}
**Expected result** — `algenta whoami` confirms you are signed in and prints the stored key's prefix, and subsequent commands run without any key flag. The stored key is picked up automatically; scripts can still read it from `$ALGENTA_API_KEY`.
{% endhint %}

{% expandable title="What algenta login does under the hood" %}
`algenta login` runs the OAuth 2.0 Device Authorization Grant against the hosted accounts service:

1. Requests a `device_code` + `user_code` and a verification URL (`accounts.thyn.ai/device`).
2. Polls for approval at the advertised interval while you confirm the code in the browser.
3. Exchanges the approved grant for a session, then mints an API key and registers this device against your plan's device limit.

The result is an ordinary Algenta API key — the same credential you can also create by hand with `POST /v1/api-keys`. See [Authentication & API keys](authentication.md) and [Device binding](guides/device-binding.md).
{% endexpandable %}

## When login does not complete

<details>
<summary>The browser never opened</summary>

Some environments block the CLI from launching a browser. Re-run with `algenta login --no-browser`, then open the printed URL yourself and enter the code.
</details>

<details>
<summary>The CLI keeps saying it is waiting</summary>

The CLI polls until you approve the code at `accounts.thyn.ai/device`. Finish the browser approval and it proceeds automatically. If the code has expired (10-minute limit), press Ctrl-C and run `algenta login` again.
</details>

<details>
<summary>You are on a self-hosted or air-gapped deployment</summary>

There is no hosted browser sign-in for private profiles. Ask your operator for an API key and export it as `ALGENTA_API_KEY`, or set an explicit `ALGENTA_BASE_URL`. See [Run air-gapped](guides/air-gapped.md).
</details>

## Next steps

<table data-view="cards"><thead><tr><th></th><th></th><th data-hidden data-card-target data-type="content-ref"></th></tr></thead>
<tbody>
<tr><td><strong>Manage your API keys</strong></td><td>Mint bounded keys, rotate, and revoke.</td><td><a href="authentication.md">authentication.md</a></td></tr>
<tr><td><strong>Explore the local algenta CLI</strong></td><td>Demo, import, and query on your machine.</td><td><a href="sdk/algenta-cli.md">sdk/algenta-cli.md</a></td></tr>
<tr><td><strong>Drive the full platform with de</strong></td><td>The complete control-plane CLI over /v1.</td><td><a href="cli.md">cli.md</a></td></tr>
</tbody></table>
