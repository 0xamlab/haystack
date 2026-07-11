---
icon: comments
description: A declarative Microsoft 365 Copilot and Teams agent that turns a conversation into a governed decision computed in your organization's Azure decision runtime
---

# Decision Agent in Copilot & Teams

The Decision Agent brings governed decisions into the tools your people already use. An employee describes a decision in Microsoft 365 Copilot or in a Teams chat, and the agent frames it, runs the analysis, and returns a recommendation with evidence and a proposed plan. Copilot frames and explains the conversation; the Decision API does the computing in your organization's Azure decision runtime.

This is a **declarative** agent: it carries a small set of instructions and a single API action, and every number it shows comes from a tool result — never from the model.

{% hint style="info" %}
Microsoft 365, Copilot, and Teams are Microsoft-hosted surfaces. The decision analysis itself runs in your organization's Azure decision plane behind your gateway, so figures are computed against your data and your operating model. Hosting the decision plane in your own Azure keeps you in control of it, but does not by itself make it network-isolated — apply your usual network controls.
{% endhint %}

## How a conversation becomes a decision

The agent is instructed to work like an analyst, not a chatbot:

1. **Frame first.** Before computing, it restates the decision as an objective, the levers you can pull, the constraints you must respect, and the assumptions in play.
2. **Run the governed analysis.** It calls the Decision API — which internally runs scenarios, simulation, optimization, and sensitivity — rather than estimating anything itself.
3. **Recommend with a reason.** It presents the recommended option, its expected outcome, the key sensitivity threshold, and why the alternatives were rejected.
4. **Cite the evidence.** When asked, it reports exactly what data was accessed and under which retention mode.
5. **Propose, never approve.** It can propose an action plan, but approving and executing that plan are separate, credentialed human actions it cannot perform.

## The operations the model can call

The agent exposes a small, coarse set of operations to Copilot. Fine-grained and administrative operations are deliberately kept out of the model's reach.

| Operation | What it does |
| --- | --- |
| `create_or_update_decision` | Frame a decision as a case with an immutable revision, or re-frame an existing case. |
| `run_decision_analysis` | Run the governed analysis for a case (evidence → scenarios → simulate → optimize → sensitivity → recommendation). Runs asynchronously — the agent starts it and polls for completion. |
| `get_decision_result` | Fetch the host-independent result object for a completed run. |
| `inspect_decision_evidence` | Return the evidence and provenance for a run: what was accessed and under which retention mode. |
| `propose_action_plan` | Propose a safe execution plan for a completed run and return a plan hash for a later human approval. |

{% hint style="warning" %}
**Approve and execute are not model-callable tools.** They are intentionally excluded from the agent's action so the model can never self-approve or self-execute. A person acts on a proposed plan with their own credentials, outside the conversation. This boundary is enforced by what the API plugin exposes, not just by the agent's instructions.
{% endhint %}

## Guardrails baked into the agent

The agent's instructions encode the trust rules directly, so behavior stays consistent across conversations:

- **Never invent numbers.** Every figure presented must come from a tool result; the decision runtime computes, the model narrates.
- **Always be able to cite evidence.** On request, the agent reports what data the run used and how confident the recommendation is.
- **Be honest about infeasibility.** If the analysis returns no feasible solution, the agent says so and shows the binding constraint instead of fabricating a recommendation.
- **Never self-approve or self-execute.** The agent may propose a plan; a credentialed person approves and executes it.
- **State the framing.** Figures are described as "model-estimated under the stated assumptions," not as guarantees.

## Identity and workspace resolution

Employees sign in with Microsoft Entra. The agent never trusts a workspace or organization value supplied by the client. Instead, the gateway derives the caller's organization and workspace from an **admin-provisioned mapping** keyed to the authenticated Entra principal.

The result: a signed-in employee only ever operates within the organization an administrator has mapped them to, and there is no client-supplied field that can widen that scope.

{% hint style="info" %}
The same Entra sign-in flow secures the Decision API across surfaces. See [Sign in with Microsoft Entra](entra-sso.md) for how identity is established and carried to the gateway.
{% endhint %}

## What an administrator does to enable it

Enabling the agent for your tenant is a set of standard enterprise admin tasks.

{% stepper %}
{% step %}
### Serve the reduced agent OpenAPI on the gateway

Expose the reduced Decision API specification — the coarse decision operations only, excluding administrative operations, low-level internals, and any approval or execution mutations — from your gateway, and record its URL for the plugin registration.

```http
GET $GATEWAY_URL/openapi/decision-agent.json
```
{% endstep %}

{% step %}
### Register the API and a client in Entra and create the plugin's OAuth registration

Register the Decision API and a client application in Microsoft Entra, then create the plugin's OAuth registration in the Microsoft 365 admin center and reference it from the API plugin. Grant admin consent so employees can use the agent without individual approvals.

You will supply your own values in place of placeholders such as `$TENANT_ID` and the OAuth registration id.
{% endstep %}

{% step %}
### Package the agent and upload it in the Microsoft 365 admin center

Assemble the agent package — the declarative agent definition, the API plugin, the Teams app manifest, and the color and outline icons — set the app id and valid domains to your gateway, and upload the package in the Microsoft 365 admin center (or build it with the Microsoft 365 Agents Toolkit).
{% endstep %}
{% endstepper %}

### Expected result

Once the package is uploaded and consented, the Decision Agent appears in Microsoft 365 Copilot and in Teams for the employees you assign. A signed-in user can open the agent, describe a decision (or pick a conversation starter such as recovering a margin gap or allocating customer-success capacity), and receive a framed recommendation with cited evidence and a proposed plan — with approval and execution left to a credentialed human.

## One Decision API, many surfaces

The Copilot and Teams agent is a thin adapter over the Decision API. The **same** API is reused by other Microsoft surfaces through their own thin adapters — including the Excel add-in for spreadsheet-driven decisions and Azure AI developer surfaces for programmatic use. Frame once, and the governed analysis behaves consistently wherever your people work.

## Next steps

- [Excel Decision Add-in](excel.md) — bring the same governed decisions into spreadsheets.
- [Sign in with Microsoft Entra](entra-sso.md) — how employees authenticate and how the gateway resolves their workspace.
- [Drive a governed decision through the API](../../guides/governed-decisions.md) — the frame → run → inspect → propose flow the agent calls under the hood.