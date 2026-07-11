# Algenta Decision Agent — Power Platform / Copilot Studio connector

Frame, run, inspect, and propose **governed decisions** on the customer-hosted Algenta gateway from
Copilot Studio, Power Automate, and Power Apps. The connector wraps the coarse Decision API
(`apiDefinition.swagger.json`) with Microsoft Entra (AAD) OAuth.

## Workflow
frame a decision → run the analysis (async) → get the result → inspect evidence → propose a plan →
record an outcome. **Approval and execution are intentionally not exposed** — they are separate,
credentialed human actions performed in Teams or Excel.

## Prerequisites
- A deployed Algenta decision gateway (`https://gateway.algenta.ai`) with Microsoft Entra sign-in on.
- The connector's own Entra client app (a registration distinct from the Decision API app), granted
  delegated `Decisions.Run` on `api://3983990d-e9b5-4866-9a43-d52d6e0c20c3` with admin consent.
- A signed-in user in an allowed tenant.

## Get a connection
On first use, sign in with Microsoft Entra; the connection acquires an access token whose audience is
`api://3983990d-e9b5-4866-9a43-d52d6e0c20c3`. The gateway maps your identity to a workspace and role.

## Known issues & limitations
- The decision runtime is customer-hosted; the connector only reaches gateways your tenant is allowed to call.
- Numeric results are model-estimated under stated assumptions, not guarantees.
