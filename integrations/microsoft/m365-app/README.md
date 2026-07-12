# Algenta Decisions — unified Microsoft 365 app package

**One** Microsoft 365 (JSON) manifest that carries **all three** Algenta Microsoft surfaces so a
single `POST /appCatalogs/teamsApps` publishes them together:

1. **Teams app** — the base app package.
2. **Microsoft 365 Copilot declarative agent** — `copilotAgents.declarativeAgents` →
   `declarativeAgent.json` → `apiPlugin.json` (the coarse Decision API action, OAuth-secured).
3. **Excel task-pane add-in** — folded into the top-level `extensions[]` block (workbook scope,
   ExcelApi 1.3, task pane at `https://addin.algenta.ai/taskpane.html`, ribbon **Home → Algenta →
   Decisions** button).

These are independent sibling root properties of the unified manifest, so they coexist in one
package with one app `id`, one `version`, one set of icons, and one SSO identity.

## Files (packaged members)
- `manifest.json` — the unified manifest (see structure below).
- `declarativeAgent.json` — the Copilot declarative agent (copied verbatim from `../copilot-agent`).
- `apiPlugin.json` — the Decision API plugin; still carries the `${{OAUTH2_REGISTRATION_ID}}`
  placeholder, substituted at package time by the deployer/packager.
- `color.png` — 192×192 full-color app icon.
- `outline.png` — 32×32 white/transparent outline icon.

The **ribbon icons and task pane** are referenced by HTTPS URL (`https://addin.algenta.ai/...`), so
they are **not** packaged in the zip — only `color.png`/`outline.png` are.

The standalone `../copilot-agent` (agent-only) and `../excel-addin` (classic XML) packages are
kept intact for reference and for the legacy/older-Office fallback path.

## Manifest structure
- `$schema` = `.../teams/v1.24/MicrosoftTeams.schema.json`, `manifestVersion` = **`1.24`**.
  v1.24 is the GA floor that carries **both** the Office-add-in `extensions` block **and**
  `copilotAgents`. (Microsoft's "combine a Copilot agent with an Office add-in" doc is written
  against `vDevPreview`/`devPreview`; that preview channel is the fallback only if a numbered
  publish is ever rejected for the combined scenario — not needed here.)
- `id` = `5a3209f0-79c2-4f05-ab1f-f0d42449dff8` — **reused** from the existing Teams/Copilot app so
  the deployer's create-or-update updates the ONE published app in place. The legacy Excel XML id
  `f445f3f1-...` is **not** a root id; it appears only inside `extensions[].alternates.hide` to
  suppress a duplicate ribbon button on clients that still have the classic add-in.
- `webApplicationInfo` (root) = `{ id: 3983990d-..., resource: api://3983990d-... }` — carries the
  add-in's SSO audience (the shared Entra app). The classic `<Scopes>` `openid/profile/access_as_user`
  are **NOT** in the manifest — they stay on the Entra app registration.
- `copilotAgents.declarativeAgents[0]` → `declarativeAgent.json`.
- `extensions[0]` — the Excel add-in: `requirements.scopes:["workbook"]` + `ExcelApi 1.3`;
  `runtimes[TaskPaneRuntime]` (page → taskpane.html, action `ShowTaskPane`); `ribbons` (Home tab,
  Algenta group, **Decisions** button whose `actionId` **must equal** the runtime action id
  `ShowTaskPane`); `alternates.hide.customOfficeAddin` → legacy XML id.
- `validDomains` = `gateway.algenta.ai`, `addin.algenta.ai`.

Icon-size note: `alternates.highResolutionIcon` max allowed size is **80** (128 is rejected; allowed
set is 16/20/24/32/40/48/64/80).

## Package & deploy
```bash
# package only (substitutes the OAuth placeholder)
python scripts/microsoft_teams_packager.py \
  --src integrations/microsoft/m365-app \
  --out build/algenta-teams-app.zip \
  --oauth-registration-id <reference_id>

# one command, one device-code sign-in — publishes Teams + Copilot + Excel in ONE Graph call
python scripts/deploy_microsoft_turnkey.py --oauth-registration-id <reference_id>
```
The deployer's `--src` defaults to this `m365-app` directory. Point it at
`integrations/microsoft/copilot-agent` for the agent-only (legacy) package.

## HONEST Excel deployment truth

**One Graph publish covers _distribution_ of all three; it does NOT put the Excel add-in on users'
ribbons.**

`POST /appCatalogs/teamsApps` only publishes the app to the org **catalog**
(`distributionMethod = organization`). That is enough for the Teams app and the Copilot declarative
agent to become usable. It is **not** a user assignment. The Excel task pane / **Decisions** ribbon
button appears only after one of:

- **Org-wide (admin, no Graph API):** Microsoft 365 admin center → **Settings → Integrated Apps** →
  find *Algenta Decisions* → **Deploy / Assign users** (Everyone or groups) → **Deploy**. There is
  **no Graph/REST API** for this assignment. Unified-manifest add-ins **cannot** be deployed from
  the legacy Add-ins portal — the Integrated Apps portal is required.
- **Per-user:** a user self-acquires the app from the store (Excel on the web → Home → Add-ins), or
  sideloads the manifest for testing.

A Teams/M365 install **alone does not** surface the Office add-in — until assigned it reads
"Not assigned" and stays off the ribbon.

Further caveats:
- **Propagation:** even after assignment the ribbon button can take **24–72 hours** to appear;
  users may need to relaunch Excel.
- **Client floor:** unified-manifest add-ins require Excel on **Windows 2501 (18407.20002)+ /
  Mac 16.103+ / web**. Perpetual, volume, mobile Office and Outlook-on-Mac are unsupported — keep
  `../excel-addin/manifest.xml` (classic XML) deployed for those users. The
  `extensions[].alternates.hide.customOfficeAddin` link prevents a duplicate "Algenta / Decisions"
  button (the link can take up to 24h to apply).
- **Sovereign/gov clouds (GCC-H/DoD):** no Integrated Apps portal — use classic Centralized
  Deployment with the XML manifest; the unified package won't serve them.
- **Plugin OAuth vault:** `apiPlugin.json` still carries `${{OAUTH2_REGISTRATION_ID}}`; mint the
  vault (`atk oauth register` or the deployer's `--register-oauth`) or the agent's authenticated
  Decision API actions won't run.
- **SSO scopes:** `openid/profile/access_as_user` live on Entra app `3983990d`, not in the manifest.
  Deleting them thinking the manifest replaces them breaks add-in SSO.

## Validation

Validate against the **authoritative live schema** (this is the source of truth for CI):
```bash
check-jsonschema \
  --schemafile https://developer.microsoft.com/json-schemas/teams/v1.24/MicrosoftTeams.schema.json \
  integrations/microsoft/m365-app/manifest.json
# -> "ok -- validation done"
```

`npx office-addin-manifest validate manifest.json` currently reports **2 false-positive errors**:
```
/extensions/0/ribbons/0/tabs/0/groups/0 must NOT have additional properties.
  Details: {"additionalProperty":"builtInGroupId"}
  Details: {"additionalProperty":"overriddenByRibbonApi"}
```
These are **not** defects in this manifest. `builtInGroupId` and `overriddenByRibbonApi` are **not**
present in the authored file (the ribbon group has only `id/label/icons/controls`). The tool's own
`readTeamsManifest`/`jsonToManifest` converter (office-addin-manifest 2.1.6 / @microsoft/app-manifest
1.0.6) **injects** those two keys with value `undefined` into every ribbon group and then its
validator flags them. Proof: the authored manifest validates **true** against the identical v1.24
schema with the same `ajv-draft-04` engine; only the converter's round-tripped object (which carries
the injected `undefined` keys) fails — JSON round-tripping it (dropping the `undefined` keys) makes
it valid again. Both the live schema and office-addin-manifest's own bundled v1.24 schema explicitly
allow `id/label/icons/controls` in `extensionRibbonsCustomTabGroupsItem`.

Prefer `check-jsonschema` against the live schema (or `atk validate`) for CI; do **not** gate on
`office-addin-manifest validate` until it stops injecting those keys. The final authoritative check
is the Graph publish itself (returns `UnableToParseTeamsAppManifest` + `SchemaError_*` on failure).
Optionally sideload the built zip in a dev tenant (`atk validate --package-file <zip>`, then
`atk install` / Excel "Upload My Add-in") to confirm the task pane loads before org rollout.
