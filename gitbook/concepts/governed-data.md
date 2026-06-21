---
icon: shield-check
description: Governed data is data Algenta queries under a typed, schema-validated, deterministic, auditable contract — sources, datasets, connectors, and the resolve to query flow.
---

# Governed data & query

Governed data is any data the Algenta engine queries under a typed, validated contract rather than free-form text. A registered **source**, an onboarded **dataset**, or a configured **connector** is profiled once: the engine infers a schema, classifies every column into a structural role, and detects join keys and derived formulas. From then on, queries are expressed as a structured spec (`source_name`, `metric_column`, `group_column`, `aggregation`, typed filters), the engine validates that spec against the known schema, and it returns a result with a `plan_hash`, a `schema_revision`, and a `validated` flag. The query is a contract, not a guess.

## Why it exists

Most "ask your data" systems translate a natural-language question directly into SQL with a model, then run whatever string comes back. That path is non-deterministic (the same question can produce different SQL on different runs), unauditable (you cannot prove why a number was produced), and unsafe (a hallucinated column or an unintended cross-source join silently returns wrong answers).

Algenta splits the responsibility. The LLM handles language: it turns the user's question into structured intent and resolves ambiguity with the user. The engine handles correctness: schema understanding, role assignment, validated execution, and a reproducible plan. Because the engine only ever executes validated structure against a known schema revision, identical intent over the same schema produces an identical result and an identical `plan_hash` every time. That is what "governed" buys you — determinism you can replay and an audit trail you can show.

{% hint style="info" %}
This is **not** LLM-to-SQL. The engine does not run model-generated query strings. It executes a typed spec it has validated against the inferred schema, so a column or join that does not exist is rejected before any data is touched, never improvised.
{% endhint %}

## Governed vs. ungoverned

| | Ungoverned (LLM-to-SQL) | Governed (Algenta) |
| --- | --- | --- |
| Input to the engine | A generated SQL string | A typed spec validated against the schema |
| Schema | Implicit, trusted | Inferred, role-classified, versioned (`schema_revision`) |
| Determinism | Same question may differ each run | Same intent + schema => identical result + `plan_hash` |
| Bad column / bad join | Runs, may return wrong rows | Rejected before execution |
| Auditability | The SQL, if you logged it | `plan`, `plan_hash`, `validated`, `decision_path`, candidates |

## The resolve to query flow

A governed query is two endpoints. `POST /v1/resolve` (tag **Semantic Query**) is a bounded, deterministic planner: it turns structured intent into an exact, executable `ResolvedPlan` using only registered-source metadata, the join graph, the planner cache, and precomputed statistics. It does not scan datasets or execute anything. `POST /v1/query` then validates and runs a plan. The recommended production path supplies exact names so neither resolver guesses.

```python title="resolve_then_query.py"
import os, httpx

base = os.environ["ALGENTA_BASE_URL"]
headers = {"Authorization": f"Bearer {os.environ['ALGENTA_API_KEY']}"}

# 1. Resolve structured intent into an exact, executable plan.
resolve = httpx.post(
    f"{base}/v1/resolve",
    headers=headers,
    json={
        "dataset_id": "bookings",
        "metric": {"role": "derived_measure", "hint": "revenue"},
        "group_by": ["customer"],
        "aggregation": "sum",
        "limit": 5,
    },
).json()

# 2. Execute the resolved plan. The engine validates it against schema_revision.
result = httpx.post(
    f"{base}/v1/query",
    headers=headers,
    json={"resolved_plan": resolve["resolved_plan"]},
).json()

print(result["validated"], result["plan_hash"], result["schema_revision"])
```

Three properties of the resolve step are guaranteed by the engine: identical `intent_signature` + `schema_revision` + scope produces identical output; ambiguity clarifies or rejects, it never widens the search; and there is no fallback to a slower planner. If confidence is too low the response sets `clarification_required` and returns ranked `candidates` so the LLM (or you) can disambiguate, rather than picking blindly.

### Exact spec vs. hint spec

Once you have read the schema (from `POST /v1/sources/register` or `GET /v1/sources/{source_id}`, tag **Source Registry**), send the **exact spec**: `source_name` plus `metric_column` and, optionally, `group_column`. This bypasses both the source resolver and the column resolver — the engine only validates the named columns exist and executes. The **hint spec** (`metric.role` + `group_by` dimension words) is the fallback for exploratory queries before the schema is known; it runs the resolvers, can be `ambiguous`, and you should migrate off it once you know the column names.

### Typed filters, roles, and joins

Filters are deterministic record predicates over normalized rows, not SQL clauses. Each `FilterConditionSpec` carries an `op` drawn from a fixed set — `eq`, `in`, `gt`, `gte`, `lt`, `lte`, `is_null`, `is_not_null` — plus a relative `time_filter` window. Metric selection is driven by structural **roles** the engine assigns during profiling (`derived_measure`, `base_measure`, `unit_measure`, `ratio`, `metric`, and the dimensional roles `identifier`, `time`, `category`, `text`), so "revenue" maps to the proven computed aggregate rather than a column that merely looks numeric. Cross-source questions use an explicit `join_path` — an ordered list of typed edges with per-hop confidence and fanout gates and a bounded hop budget (4 by default, 6 maximum) — so a multi-hop join is itself part of the validated contract, not an emergent side effect.

## Use this when

- You need the **same question to return the same number every time** — for reporting, reconciliation, or anything you have to defend later.
- You want an **audit trail**: a `plan`, a stable `plan_hash`, a `schema_revision`, and the candidate columns the engine considered.
- You are wiring an **LLM or agent to your data** and want the model to own language while the engine owns schema correctness and execution.
- Your data spans **multiple registered sources** and you need joins to be explicit, confidence-gated, and rejected when ambiguous rather than silently fanned out.
- You are onboarding data through a **connector** (warehouse, SQL database, object store, REST, or file) and want it queryable under one validated contract regardless of origin.
- You explicitly do **not** want model-generated SQL strings executing against production data.

## Next

{% content-ref url="capability-plane.md" %}
[capability-plane.md](capability-plane.md)
{% endcontent-ref %}

{% content-ref url="../api/reference.md" %}
[reference.md](../api/reference.md)
{% endcontent-ref %}
