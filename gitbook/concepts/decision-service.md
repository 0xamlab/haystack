---
icon: scale-balanced
description: How Algenta turns enterprise data and operating models into governed, versioned, reproducible decisions instead of one-off chat answers
---

# The governed decision lifecycle

Most analytics tools give you an *answer*. Algenta gives you a *decision* — one you can defend, reproduce, approve, act on, and later measure against what actually happened.

The Algenta Decision Service takes your enterprise data and your operating model (how your business actually trades off cost, risk, capacity, and revenue) and drives them through a governed lifecycle. At every step the numbers are computed by an engine, framed by a language model, and recorded as an immutable, versioned trail. The result is a decision that carries its own evidence, its own assumptions, and its own approval — not a paragraph of confident prose.

{% hint style="info" %}
The language model **frames and explains**; the engine **computes**. The model never invents numbers — every figure in a recommendation traces back to a deterministic engine result. This separation is what makes an Algenta decision auditable.
{% endhint %}

## Four levels of a decision

A governed decision moves through four levels. Each one builds on the last, and each one is captured on the record so you can inspect exactly how the recommendation was reached.

{% stepper %}
{% step %}
### Understand

Gather the evidence, compute the metrics, and diagnose the situation. Algenta pins the source data, scores its quality, and separates observed facts from assumptions before any recommendation is formed. Accounts or records missing required evidence are excluded rather than silently guessed at, and the data-quality score is downgraded accordingly.
{% endstep %}

{% step %}
### Simulate

Explore scenarios, forecasts, and sensitivity. The engine runs the operating model across the option space — what happens if you shift capacity here, tighten a constraint there — and reports how sensitive the outcome is to each assumption. When the constraints admit **no feasible solution**, that is a first-class result, not a fabricated answer.
{% endstep %}

{% step %}
### Decide

Rank the options, optimize against the objective, and surface a recommendation with its trade-offs. The recommendation names the chosen option, the runner-up scenarios, and the constraints that shaped the choice — so a reviewer can see not just *what* was recommended but *why*, and what was given up.
{% endstep %}

{% step %}
### Act and learn

Turn the recommendation into a safe execution plan, route it through a separate approval, act on it, and monitor the outcome. Later, you record what actually happened and Algenta computes the delta against what was estimated — closing the loop between the decision and its result.
{% endstep %}
{% endstepper %}

## The versioned decision aggregate

Under the surface, a decision is not a single document — it is a chain of linked, versioned records. Each record has a single job, and each one is written once and never silently rewritten.

| Record | What it is | Why it matters |
|---|---|---|
| **Decision Pack** | A reusable template that encodes an objective, the levers you control, the hard constraints, and the assumptions | One vetted model, used across many decisions of the same kind |
| **Case** | One decision in flight | Permanently bound to its Pack, so its history can never drift to a different model |
| **Revision** | An immutable snapshot of the framing — objective, levers, constraints, assumptions | Editing the framing creates a *new* revision; the old one stays on the record |
| **Evidence Snapshot** | The source data and its provenance for a run | Lets a run be reproduced or audited against exactly what it saw |
| **Analysis Run** | One execution of the Pack against a revision | Carries the model version, an inputs fingerprint, a result fingerprint, and a reproducibility id |
| **Recommendation** | The ranked options, the trade-offs, and the plain-language explanation | The engine's numbers, framed for a human decision-maker |
| **Execution Plan** | A concrete, safe set of proposed actions | Fingerprinted and single-use, so an approval binds to exactly this plan |
| **Approval** | A separately authenticated sign-off on a specific plan | Proves *who* approved *what*, under *which* role |
| **Outcome** | What actually happened, recorded after the fact | Feeds the learning loop with a measured delta |

Because the chain is versioned, you can always answer "how did we decide this?" — pointing to the exact revision, evidence, model version, and approval that produced it.

## Governance properties, stated plainly

These are the guarantees the Decision Service enforces — not conventions the model is asked to follow, but rules the system holds to.

{% hint style="warning" %}
**Editing an assumption creates a new revision — never a silent mutation.** Change the objective, a lever, a constraint, or an assumption and Algenta writes a *new* immutable revision. The prior revision, and every run and recommendation attached to it, stays intact and inspectable.
{% endhint %}

- **A material change invalidates a prior approval.** If the framing is revised after a plan was approved, that approval no longer applies. You must re-propose and re-approve against the current revision — a decision can never be executed on stale terms.
- **The model frames; the engine computes.** Every material number in a narrative must exist in the engine's output. A governance check rejects any recommendation that cites a figure the engine did not produce, so the language model cannot round, embellish, or invent a value.
- **Every result carries its lineage.** A completed run records its model version, the assumptions it ran under, the source data it saw, a timestamp, and a reproducibility id derived from its inputs and its result. Re-running identical inputs must reproduce an identical result.
- **Approval is a separate, authenticated action.** Approving is not something the language model can do as a tool call. It is an explicit, role-gated step by an authorized person, bound to one exact plan by a fingerprint and a single-use challenge that expires.
- **Approve is not the same as execute.** Approval authorizes a plan; execution is a distinct step that runs only after approval and produces its own receipt. The two are never collapsed into one click.

Algenta also runs a suite of defensibility checks over each decision: that no recommended option violates a hard constraint, that provenance and a data-quality score are present, that the same inputs replay to the same result, and that free-text fields (like account names or notes) cannot move the numbers. A decision that fails these checks is flagged, not shipped.

{% hint style="info" %}
**Numbers stay honest.** Results are stated as *model-estimated under the stated assumptions* — for example, "estimated retained revenue under the stated intervention assumptions," and "met the target in N of the tested scenarios," never "N% probability" or "we will retain $X." Every figure is labelled as an observed fact, a customer assumption, an estimated parameter, or a simulated outcome.
{% endhint %}

## How this differs from conversational BI

A conversational BI tool answers a question in a chat window. The answer looks authoritative, but it is ephemeral: there is no revision history, no pinned evidence, no reproducibility id, no separate approval, and no record of whether the numbers came from your data or from the model's guesswork.

An Algenta decision is the opposite:

| Conversational BI | Algenta Decision Service |
|---|---|
| One-off answer in a chat thread | A versioned decision you can revisit and reproduce |
| Model may state numbers it inferred | Every number is computed by the engine and traced |
| No record of assumptions or sources | Evidence, assumptions, and model version pinned to each run |
| Approval is implied, never proven | Approval is a separate, authenticated, role-gated act |
| No follow-through | A safe execution plan and a measured outcome close the loop |

The point is not to replace the conversation — the language model still frames the problem and explains the trade-offs in plain language. The point is that behind the conversation sits a governed, computed, reproducible decision your auditors, your leadership, and your future self can trust. For customers running on Microsoft Cloud, that computation happens in the decision runtime inside your own Azure tenant, while Microsoft 365, Teams, and Copilot remain Microsoft-hosted surfaces.

## Next steps

- [Drive a governed decision through the API](../guides/governed-decisions.md)
- [Renewal Capacity Allocation pack](../guides/renewal-capacity-allocation.md)
- [Algenta for Microsoft Cloud](../integrations/microsoft/overview.md)