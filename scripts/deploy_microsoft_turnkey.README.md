# deploy_microsoft_turnkey.py — the "1 click for all" Microsoft deployer

One command, one interactive device-code sign-in. Publishes the Algenta Teams app **and** the
Microsoft 365 Copilot declarative agent (they ride the same app package) to the org catalog,
installs it for the signed-in admin, and prints the exact minimal residual for anything Microsoft
has no API for (the Excel SSO add-in org-wide push).

## Prerequisites

```bash
pip install msal requests
```

Pin (matches this repo's verified versions):

```
msal>=1.28,<2
requests>=2.31,<3
```

The deployer public-client app is already provisioned + admin-consented in the thyn.ai tenant and
its client id (`263fd674-345d-4dca-abed-6787959e9be7`) is baked in as the default, so no env setup
is needed. To (re)provision for a different tenant/app:

```bash
az login                                        # as a Global / Cloud Application Admin
python scripts/provision_microsoft_deployer.py  # creates + admin-consents the deployer app (uses az token)
export ALGENTA_MS_DEPLOYER_CLIENT_ID=<id printed above>
```

## The single run command

```bash
python scripts/deploy_microsoft_turnkey.py
```

Sign in ONCE at `https://login.microsoft.com/device` with the code the script prints (the token is
cached 0600 at `~/.algenta_ms_deployer_cache.json`, so re-runs need no sign-in). Re-runnable: on a
first run it publishes; on later runs it updates the catalog app and **auto-bumps the version** off
the currently-published one (Graph rejects an update whose version isn't strictly higher), and it
treats "already installed" as success.

## Useful flags / env

| Flag | Env | Effect |
|---|---|---|
| `--client-id` | `ALGENTA_MS_DEPLOYER_CLIENT_ID` | deployer public-client app id (defaults to the provisioned app) |
| `--oauth-registration-id` | `OAUTH2_REGISTRATION_ID` | the plugin's OAuth/SSO vault `reference_id`; substituted into `apiPlugin.json` before zipping |
| `--register-oauth` | — | best-effort: create the vault in the same sign-in (degrades to a residual) |
| `--require-oauth` | — | refuse to publish if the `reference_id` is unresolved |
| `--bump` | — | force a patch bump on the *first* publish (updates auto-bump off the published version already) |
| `--install-for USER_ID\|UPN` | — | install for someone other than the signer (needs one sign-in per user) |
| `--dry-run` | — | package only; make no Graph writes |

If no OAuth `reference_id` is available the agent still publishes and appears; only its
authenticated Decision API actions stay dormant until the vault is registered.

## What is automated vs residual

- **Automated (Graph v1.0):** publish/update the org-catalog Teams app + M365 Copilot declarative
  agent, and install it for the signed-in admin.
- **Residual (no API):** Excel SSO add-in org-wide push — the script prints the exact
  admin.microsoft.com → Integrated apps step plus the immediate per-user "Upload My Add-in" test.
- **Best-effort:** the plugin OAuth/SSO vault `reference_id` (supply via flag/env, or
  `atk oauth register`).

See `integrations/microsoft/DEPLOY.md` for the full matrix and the honest residuals.
