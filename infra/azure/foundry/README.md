# Algenta Decision Agent — Azure AI Foundry integration

Register Algenta as a **governed decision tool** in an Azure AI Foundry project. Foundry governs
the *models* (deployment, evaluation, tracing); Algenta governs the *decisions* (structure,
constraints, simulation, recommendation, evidence, approval). Foundry **calls** the Decision API —
it does not sit beneath the engine.

The agent frames + explains; the engine computes in the customer's Azure. The agent-facing surface
is the **reduced** Decision API spec — coarse operations only. Approval mutation, plan execution,
admin, and workspace selection are structurally absent from what an agent can call.

## Contents

| Path | What it is |
|---|---|
| `agent-definition/decision-agent.json` | The Foundry agent (instructions + guardrails + the OpenAPI tool + service identity). |
| `tool-definition/decision-tool.json` | The OpenAPI tool pointing at the gateway's `GET /openapi/decision-agent.json`. |
| `evaluations/decision_evaluators.json` | Catalog of the decision-specific evaluators for a Foundry evaluation run. |
| `evaluations/run_evals.py` | Offline harness that scores decision results with those evaluators. |
| `evaluations/cases.json` + `sample-data/` | A clean decision (passes) and a seeded-violation decision (must be flagged). |

## Dual identity

- **Service / managed identity** — Foundry testing, scheduled evaluations, automated refresh, and
  org-scoped agents. The gateway maps the identity to a restricted workspace + app-role.
- **Delegated employee identity** — user-initiated decisions, where Foundry propagates the
  originating employee's audience-scoped Entra token.

In both cases the gateway validates issuer, **audience** (`api://$GATEWAY_AUDIENCE`), tenant, scope
/ app-role, and signing key, and rejects a Microsoft Graph token or an Azure-management token.

## The decision-evaluation pack

Generic evals score language quality. These score whether a **governed decision is defensible**:

| Evaluator | Fails when |
|---|---|
| `constraint_compliance` | a recommended option violates a hard constraint |
| `numerical_grounding` | the narrative cites a figure the engine did not produce |
| `evidence_coverage` | provenance or a data-quality score is missing |
| `no_feasible_solution` | an infeasible run fabricates a recommendation |
| `unit_consistency` | a probability/utilization is out of [0,1] or ARR/hours is negative |
| `deterministic_replay` | identical inputs produce a different result |
| `instruction_isolation` | changing free-text fields moves the numbers (prompt injection) |

Run it offline:

```bash
python infra/azure/foundry/evaluations/run_evals.py
```

Expected output — the clean decision passes and the seeded violation is caught:

```text
OK renewal_clean                verdict=pass expect=pass {'passed': 5, 'failed': 0, 'skipped': 2}
OK renewal_seeded_violation     verdict=fail expect=fail {'passed': 2, 'failed': 2, 'skipped': 3}
     - [high] constraint_compliance: hard constraint(s) not satisfied: total_capacity
     - [high] unit_consistency: recommended: capacity_utilization 1.5 out of [0,1]; ...
RESULT: all cases matched expectations
```

These are the same evaluators the engine runs in-process — the harness just wraps them so a Foundry
evaluation (or CI) can score decision outputs offline.

## Setup (admin)

1. **Deploy the gateway** into your Azure and note its URL and Entra audience — see
   [Deploy the decision gateway to your Azure](../../../gitbook/integrations/azure/gateway.md).
2. **Serve the reduced spec** — the gateway exposes `GET /openapi/decision-agent.json` already; set
   `spec_url` in `tool-definition/decision-tool.json` to `https://<your-gateway>/openapi/decision-agent.json`.
3. **Grant the Foundry identity** a mapping to a restricted workspace + app-role on the gateway, and
   set the tool `auth.audience` to `api://<your-gateway-audience>`.
4. **Set the model deployment** in `agent-definition/decision-agent.json`, then register the agent
   in your Foundry project and add the evaluators from `evaluations/decision_evaluators.json`.

> The exact Foundry resource/agent/tool field names track the current Foundry project model; the
> JSON here is aligned to that shape — validate against your project before deploying. An
> infrastructure template for the Foundry project itself is intentionally left for the owner to
> pin once the target Foundry API version is fixed.
