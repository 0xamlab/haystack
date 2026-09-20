---
icon: comments
description: A declarative Microsoft 365 Copilot and Teams agent that connects to your Algenta runtime over the Model Context Protocol and turns a conversation into a computed decision
---

# Decision Agent in Copilot & Teams

The Decision Agent brings governed decisions into the tools your people already use. An employee describes a decision — or drops in a spreadsheet — in Microsoft 365 Copilot or a Teams chat, and the agent frames it, calls the engine, and returns a recommendation with the numbers behind it. Copilot frames and explains the conversation; the Algenta engine does the computing in your organization's Azure.

This is a **declarative** agent connected to Algenta through the **Model Context Protocol (MCP)**. It carries a small set of instructions and a single MCP action that exposes a curated set of decision and simulation tools. Every number it shows comes from a tool result — never from the model.

{% hint style="info" %}
Microsoft 365, Copilot, and Teams are Microsoft-hosted surfaces. The analysis itself runs on the Algenta engine behind your gateway, in your organization's Azure, so figures are computed against your data and your operating model. Hosting the engine in your own Azure keeps you in control of it, but does not by itself make it network-isolated — apply your usual network controls.
{% endhint %}

## How a conversation becomes a decision

The agent is instructed to work like an analyst, not a chatbot:

1. **Frame first.** Before computing, it restates the request as an objective, the levers you can pull, and the constraints and assumptions in play.
2. **Call the engine.** It calls an Algenta tool over MCP — the engine runs the real simulation, optimization, or forecast — rather than estimating anything itself.
3. **Recommend with a reason.** It presents the recommended option, its expected outcome, the key risk or sensitivity, and why alternatives were rejected.
4. **Stay grounded.** Every figure it reports is a computed tool result, labelled "model-estimated under the stated assumptions."
5. **Propose, never approve.** It can propose an action plan, but approving and executing that plan are separate, credentialed human actions it cannot perform.

## Run a simulation on your spreadsheet

Because the agent connects over MCP, it can pass a table of your data straight to the engine. Attach or paste a spreadsheet — transactions, a budget, a list of accounts — and ask the agent to simulate or stress-test it. The `ingest_data` tool auto-detects the variable distributions from your rows and runs a real Monte Carlo, so you get a computed outcome distribution rather than a guess. When you instead state the drivers and their ranges directly ("revenue 80k–120k, cost 40k–60k"), the agent uses `simulate`.

## The tools the agent can call

The agent exposes a small, curated set of tools to Copilot. The engine hosts many more, but the agent is deliberately limited to a focused decision surface so the model routes reliably.

| Ask the agent to… | Tool it calls |
| --- | --- |
| Simulate or stress-test a table/spreadsheet of data | `ingest_data` |
| Run a Monte Carlo from named drivers with low/high ranges | `simulate` |
| Decide what to cut, allocate, or choose to hit a target under constraints | `product_optimize` |
| Project a metric (spend, burn, revenue, runway) over future periods | `product_forecast` |
| Rank candidate actions or options by simulated outcome | `recommend` |
| Compare named scenarios side by side | `compare` |
| Get a quick decision from inputs and an objective | `product_decision` |
| Record a decision to the audit trail | `log_decision` |

{% hint style="warning" %}
**Approve and execute are not model-callable tools.** They are intentionally excluded from the agent's tool set so the model can never self-approve or self-execute. A person acts on a proposed plan with their own credentials, outside the conversation. This boundary is enforced by what the MCP action exposes, not just by the agent's instructions.
{% endhint %}

## Guardrails baked into the agent

The agent's instructions encode the trust rules directly, so behavior stays consistent across conversations:

- **Never invent numbers.** For any quantitative request the agent must call a tool and report its output; the engine computes, the model narrates.
- **Never fabricate inputs.** If a required input is genuinely missing, the agent asks for it rather than inventing a range or a distribution.
- **Be honest about infeasibility.** If the analysis returns no feasible solution, the agent says so and shows the binding constraint instead of fabricating a recommendation.
- **Never self-approve or self-execute.** The agent may propose a plan; a credentialed person approves and executes it.
- **State the framing.** Figures are described as "model-estimated under the stated assumptions," not as guarantees.

## Identity and workspace resolution

Employees sign in with Microsoft Entra. Copilot acquires an Entra token for the Algenta engine and presents it on every MCP call, so tools run as the signed-in user. The agent never trusts a workspace or organization value supplied by the client — the gateway derives the caller's organization and workspace from an **admin-provisioned mapping** keyed to the authenticated Entra principal.

The result: a signed-in employee only ever operates within the organization an administrator has mapped them to, and there is no client-supplied field that can widen that scope.

{% hint style="info" %}
The same Entra sign-in secures the engine across surfaces. See [Sign in with Microsoft Entra](entra-sso.md) for how identity is established and carried to the gateway.
{% endhint %}

## What an administrator does to enable it

Enabling the agent for your tenant is a set of standard enterprise admin tasks.

{% stepper %}
{% step %}
### Expose the MCP endpoint on your gateway

The engine serves a Model Context Protocol endpoint over Streamable HTTP. Confirm it is reachable on your gateway and record its URL for the plugin registration.

```http
POST $GATEWAY_URL/mcp
```
{% endstep %}

{% step %}
### Register the API and a client in Entra and create the OAuth registration

Register the Algenta API and a client application in Microsoft Entra, then create the plugin's OAuth registration (Entra single sign-on) in the Teams Developer Portal and reference it from the MCP action. Grant admin consent so employees can use the agent without individual approvals.

You supply your own values in place of placeholders such as `$TENANT_ID` and the OAuth registration id.
{% endstep %}

{% step %}
### Package the agent and upload it in the Microsoft 365 admin center

Assemble the agent package — the declarative agent definition, the MCP plugin manifest (a `RemoteMCPServer` runtime pointing at `$GATEWAY_URL/mcp`), the app manifest, and the color and outline icons — set the app id and valid domains to your gateway, and upload the package in the Microsoft 365 admin center (or build it with the Microsoft 365 Agents Toolkit).
{% endstep %}
{% endstepper %}

### Expected result

Once the package is uploaded and consented, the Decision Agent appears in Microsoft 365 Copilot Chat and in Teams for the employees you assign. Select `@Algenta`, describe a decision or attach a spreadsheet, and the agent calls the engine over MCP and returns a computed recommendation — with approval and execution left to a credentialed human.

{% hint style="info" %}
MCP actions are available to a declarative agent **inside Copilot Chat / BizChat and Teams**, not in base Copilot. Select the `@Algenta` agent (rather than plain Copilot) so its tools are in scope, and use a fresh chat after a new version is published.
{% endhint %}

## One engine, many surfaces

The Copilot and Teams agent is a thin adapter over the Algenta engine. The **same** engine and MCP surface are reused by other clients — including the Excel add-in for spreadsheet-driven decisions, editors and agents that speak MCP, and the SDKs. Frame once, and the analysis behaves consistently wherever your people work.

## Next steps

- [Excel Decision Add-in](excel.md) — bring the same governed decisions into spreadsheets.
- [Sign in with Microsoft Entra](entra-sso.md) — how employees authenticate and how the gateway resolves their workspace.
- [MCP server](../../sdk/mcp.md) — connect any MCP client to the same tool surface.
