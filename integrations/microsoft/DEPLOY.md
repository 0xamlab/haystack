# Algenta — "1 click for all" Microsoft deploy

One command, one interactive device-code sign-in. It publishes **one unified Microsoft 365 app**
(`integrations/microsoft/m365-app/`) that carries all three surfaces in a single package —

- the **Teams** app,
- the **Microsoft 365 Copilot** declarative agent + Decision API plugin, and
- the **Excel** task-pane add-in (`extensions[]`) —

to your org catalog and installs it for you, via Microsoft Graph.

## The one command

The deployer app is already provisioned + admin-consented in the thyn.ai tenant
(`Algenta Microsoft Deployer`, appId `263fd674-345d-4dca-abed-6787959e9be7`, baked in as the
default), so this is genuinely one argument-free command — **run it as a Global admin** so the Graph
org-catalog publish doubles as the Copilot Control System approval:

```bash
pip install msal requests   # once, if not already present
python scripts/deploy_microsoft_turnkey.py
```

Then **sign in ONCE** at `https://login.microsoft.com/device` with the code it prints — that is the
only interactive step.

<details><summary>Re-provisioning the deployer app (only needed for a different tenant/app)</summary>

```bash
python scripts/provision_microsoft_deployer.py            # uses your `az login` token
export ALGENTA_MS_DEPLOYER_CLIENT_ID=<id printed above>   # or pass --client-id
```
</details>

Add the plugin's OAuth/SSO registration id if you have it (so the agent's authenticated actions run):

```bash
python scripts/deploy_microsoft_turnkey.py --oauth-registration-id <reference_id>
# or attempt to create it in the same sign-in (best-effort):
python scripts/deploy_microsoft_turnkey.py --register-oauth
```

## `@Algenta` — the zero-residual conversational path (the big win)

Because Algenta ships a **declarative agent** (not a custom-engine agent), publishing + installing the
unified app is *enough* for a user to open **Copilot inside Teams, the M365 Copilot app, Outlook,
Word, PowerPoint, and Excel**, type **`@Algenta …`**, and have the Decision API actions run — with
**SSO** (the M365 identity flows through the shared Entra app `3983990d` → your `EntraPrincipalMapping`
→ org, no second login). This needs **no M365 admin center / Integrated Apps assignment** — unlike the
classic ribbon add-in. The one command fully covers it.

| Surface | `@Algenta …` conversational | Covered by the one command? |
|---|---|---|
| Teams / M365 Copilot app / Outlook | ✅ @-mention + SSO plugin actions | ✅ publish + install |
| Word / PowerPoint Copilot pane | ✅ @-mention + reads the open doc | ✅ publish + install |
| **Excel Copilot pane** | ✅ @-mention + SSO plugin actions | ✅ publish + install |

**Excel functional caveat (Microsoft platform limit, not ours):** in Excel the declarative agent gets
**no workbook context** — document read/selection is Word/PowerPoint only. So `@Algenta` in Excel is
conversational (frame a decision, run the governed analysis, read the result, inspect evidence,
propose a plan); it **cannot read your selected range or write results into cells**. That grid
read/write is exactly what the **task-pane add-in** provides (below).

## What the one sign-in deploys (via Microsoft Graph v1.0)

| Surface | Action | Automated? |
|---|---|---|
| Unified M365 app | publish to org catalog — create-or-update, auto-bumps version (`POST /appCatalogs/teamsApps`, or `.../{id}/appDefinitions`) | ✅ |
| M365 Copilot declarative agent + API plugin | rides inside the unified package (`copilotAgents.declarativeAgents`) — `@Algenta` everywhere, SSO | ✅ |
| Excel task-pane add-in | rides inside the **same** package (`extensions[]`) — published to the catalog in the same call | ✅ (publish) |
| Per-user install | `POST /users/{me}/teamwork/installedApps` for the signed-in admin | ✅ |
| Plugin OAuth/SSO vault | `--oauth-registration-id` (recommended) or best-effort `--register-oauth` | ⚠️ best-effort |
| Excel **ribbon** task-pane visibility | needs one Integrated Apps **assignment** of the already-published app — **no Graph API** | ❌ residual |

The deployer is a dedicated Entra **public-client** app in tenant `7a0cd533-…` (thyn.ai). Its
least-privilege delegated scopes (`AppCatalog.ReadWrite.All`, `TeamsAppInstallation.ReadWriteForUser`,
`User.Read`) are pre-consented once, so the runtime sign-in shows no consent wall. As a public client
with no secret, it can act only when a human interactively signs in.

## Honest residuals (Microsoft has no API for these)

1. **Excel *ribbon* task-pane assignment.** The unified add-in is **already published** by the one
   command (no separate manifest to upload). For its **Decisions** ribbon button to appear in users'
   Excel, an admin must **assign the already-published app** — no Graph/REST API exists for this step:
   - **admin.microsoft.com → Settings → Integrated apps →** find **"Algenta Decisions"** (already in
     *Available apps*) **→ Deploy →** assign *Everyone*/groups. (Do **not** upload
     `excel-addin/manifest.xml` here — that classic XML add-in has a *different* id and would create a
     **duplicate** "Decisions" button; the unified package's `alternates.hide` already suppresses the
     legacy one.)
   - Ribbon appears in ~24–72h; users may need to relaunch Excel. Requires Excel Win 2501+/Mac 16.103+/web.
   - **Immediate per-user test (no admin):** Excel on the web → Home → Add-ins → Upload My Add-in →
     `excel-addin/manifest.xml`.
   - **You may not need this at all** if the conversational `@Algenta` Copilot path (above) covers the
     use case — the ribbon add-in is only for in-cell/grid read-write.

   <details><summary>Legacy / older-Office / GCC-High fallback</summary>

   Perpetual, volume, mobile Office, and sovereign (GCC-H/DoD) clients can't load the unified-manifest
   add-in. For those, deploy the **classic XML** `integrations/microsoft/excel-addin/manifest.xml` via
   Integrated Apps (or Centralized Deployment). Deploy *either* the unified or the classic add-in to a
   given user, never both.
   </details>

2. **Plugin OAuth/SSO vault (`reference_id`).** The agent publishes and appears without it, but its
   authenticated Decision API actions won't run until the vault exists (first call otherwise shows a
   per-user OAuth consent card). Creation lives on the Teams Developer Portal API, a different
   resource; fastest reliable path is `atk oauth register` under the same sign-in → pass the returned
   id to `--oauth-registration-id`. `--register-oauth` attempts it and degrades to this residual.

3. **M365 Copilot license.** The in-app Copilot pane in Excel/Word/PowerPoint is a **licensed** M365
   Copilot feature (already held by thyn.ai / angel@thyn.ai). Free Copilot Chat alone doesn't unlock it.

4. **Installing for users other than the signer.** One delegated sign-in installs into the signer's
   own Teams. Proactively installing for arbitrary users needs app-only
   `TeamsAppInstallation.ReadWriteForUser.All`, or one delegated sign-in per user.

## Packages & files

- `integrations/microsoft/m365-app/` — **the unified package the deployer publishes** (manifest.json
  v1.24 carrying `copilotAgents` + `extensions[]` + `webApplicationInfo`, declarativeAgent.json,
  apiPlugin.json, icons). Validated against the live v1.24 Teams schema via `check-jsonschema`.
- `integrations/microsoft/copilot-agent/` — agent-only package (reference / `--src` override).
- `integrations/microsoft/excel-addin/` — classic XML add-in (legacy/older-Office fallback + per-user test).
- `scripts/deploy_microsoft_turnkey.py` — the 1-click deployer (MSAL device code → package → publish → install).
- `scripts/provision_microsoft_deployer.py` — one-time: create + admin-consent the deployer app (az token).
- `scripts/microsoft_teams_packager.py` — builds the app-package zip (never mutates the source tree).

Requires `msal` and `requests`.

> Note on validators: `check-jsonschema` against the live v1.24 schema (and `atk validate`) are
> authoritative. `office-addin-manifest validate` reports 2 false positives on the combined
> agent+add-in manifest (its bundled converter injects `builtInGroupId`/`overriddenByRibbonApi` then
> flags them) — do not gate CI on it. Before broad rollout, do one real sideload/Graph publish in a
> dev tenant to confirm the host accepts the combined package (the agent+add-in combo is documented
> against `devPreview`; this package uses numbered GA v1.24, with `devPreview` as the documented
> fallback if a publish is ever rejected).
