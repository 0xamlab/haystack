# Algenta Decisions — Excel Add-in

A native Excel task pane over the customer-hosted Decision API (Build order 8). Select ranges as
a Decision Pack's assumptions, run the governed analysis in your Azure, and write results to new
sheets after a preview.

## Files
- `manifest.xml` — Office Add-in manifest (task pane + Entra SSO via `<WebApplicationInfo>`).
- `taskpane.html` / `taskpane.js` — the pane UI + the Office.js flow (SSO → read selection →
  `POST /v1/decision-cases` → run (202 + poll) → write `Algenta Decision` / `Allocation Plan` /
  `Sensitivity` / `Evidence` sheets → propose → approve).

## Trust behavior (built in)
Selection-only (never the whole workbook) · a "data to be sent" preview before any call ·
compute in your Azure · results write to **new** sheets (never overwrite) · edit-and-rerun makes
a **new** sheet · approval is a separate explicit click carrying the plan hash + single-use nonce.

## Owner go-live (Phase-0 gate)
1. **Host the static files** (`taskpane.html`, `taskpane.js`, `/assets/*`) on HTTPS; set that host
   in `SourceLocation` / the `Taskpane.Url` + icon URLs in `manifest.xml`.
2. **Entra SSO** — set `<WebApplicationInfo><Id>` to the gateway app registration's client id and
   `<Resource>` to `api://<your gateway audience>` (== `ALGENTA_ENTRA_AUDIENCE`). Pre-authorize the
   Office client ids and grant admin consent for `access_as_user`.
3. **Sideload / publish** — validate with `npx office-addin-manifest validate manifest.xml`, then
   sideload for testing or upload to the M365 admin center for the org.

The pane's "Gateway URL" field points at your deployed gateway (`infra/azure` output `gatewayUrl`).
