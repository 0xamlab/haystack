# Algenta Decision Agent — Microsoft 365 Copilot / Teams

A **declarative** Copilot agent that turns conversation into governed decisions by calling the
customer-hosted Decision API (Build order 8). Copilot frames + explains; Algenta computes in the
customer's Azure. The custom-engine agent (private networking) is the Phase-2 follow-on.

## Files
- `declarativeAgent.json` — the agent: instructions (frame → run → recommend → cite evidence;
  never invent numbers; never self-approve/execute), conversation starters, and the API action.
- `apiPlugin.json` — the coarse Decision API action (create_or_update_decision,
  run_decision_analysis, get_decision_result, inspect_decision_evidence, propose_action_plan),
  OAuth-secured, pointing at the gateway's **reduced** agent OpenAPI. **Approve/execute are NOT
  exposed** — they are separate credentialed human actions.
- `manifest.json` — the M365 app package manifest embedding the declarative agent.

## Owner go-live (Phase-0 gate)
1. **Serve the reduced spec** — expose `GET /openapi/decision-agent.json` on the gateway (only the
   ~5 coarse ops; excludes admin/engine/approval-mutation) and set its URL in `apiPlugin.json`.
2. **Entra OAuth for the plugin** — register the API + a client, create the plugin OAuth
   registration in the Teams admin center, and put its id in `apiPlugin.json`
   (`auth.reference_id`). Grant admin consent.
3. **Package + upload** — add `color.png`/`outline.png` icons, set the app `id` + `validDomains`,
   zip (`manifest.json` + `declarativeAgent.json` + `apiPlugin.json` + icons), and upload to the
   M365 admin center (or build with the M365 Agents Toolkit).

## Notes
The agent authenticates employees with Entra; the gateway derives their org/workspace from the
provisioned `entra_principal_mappings` (never a header). Figures shown are model-estimated under
the stated assumptions. Azure AI Foundry / Copilot Studio / Power Platform reuse the **same**
Decision API via their own adapters (Phase 1.5).
