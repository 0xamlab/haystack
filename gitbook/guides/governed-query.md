---
icon: table-list
description: Run a deterministic governed query end to end — resolve structured intent into an exact plan, execute it with typed filters, and read plan_hash and validated.
---

# Query governed data

This guide walks you through the full governed-query flow against a registered source — resolve structured intent into an exact, executable plan, run it with typed filters, and read back the audit fields (`plan_hash`, `schema_revision`, `validated`) that make the result reproducible. By the end you will have a number you can defend and replay. Prerequisites: an API key (see [Authentication](../authentication.md)) and one already-registered source or onboarded dataset — registration returns the `dataset_id` and the inferred `schema` (column names and roles) you will reference below.

{% hint style="info" %}
This is not LLM-to-SQL. `POST /v1/query` accepts a typed spec the engine validates against the inferred schema; it never executes a model-generated query string. A column or join that does not exist is rejected before any data is read. See [Governed data](../concepts/governed-data.md).
{% endhint %}

{% stepper %}
{% step %}
### Read the schema you will query against

You need the source's exact column names and their structural roles. Registration (`POST /v1/sources/register`) returns them in `schema.columns`; you can also re-read them later with `POST /v1/sources/schema` (tag **Semantic Query**), which returns each source's `schema` plus `query_hints`.

```bash title="read-schema.sh"
curl -s -X POST "$ALGENTA_BASE_URL/v1/sources/schema" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{}'
```

Verify: the response lists your source under `sources[]` with a `schema.columns[]` array. Note one column whose `role` is `derived_measure` (a formula-proven aggregate such as revenue) and one whose `role` is `category` or `identifier` to group by. You will use these exact `name` values as `metric_column` and `group_column`.
{% endstep %}

{% step %}
### Resolve structured intent into an exact plan

`POST /v1/resolve` (tag **Semantic Query**) is a bounded, deterministic planner: it turns structured intent into an exact `resolved_plan` using only registered-source metadata, the join graph, the planner cache, and precomputed statistics. It does not scan datasets or execute anything. Scope it with `dataset_id`, or set `allow_org_scope=true` to plan across all visible datasets.

```python title="resolve.py"
import os
import httpx

base = os.environ["ALGENTA_BASE_URL"]
headers = {"Authorization": f"Bearer {os.environ['ALGENTA_API_KEY']}"}

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

print(resolve["clarification_required"], resolve["intent_signature"])
```

Verify: the response includes a `resolved_plan` object (carrying `source_name`, `metric_column`, `group_column`, and `schema_revision`) and `clarification_required` is `false`. If it is `true`, the planner was not confident — read the ranked `candidates` and disambiguate; the planner never widens its search or falls back to a slower path.
{% endstep %}

{% step %}
### Execute the plan with the exact spec

Send the column names back to `POST /v1/query`. The recommended production path is the **exact spec**: `source_name` plus `metric_column`, and optionally `group_column`. This bypasses both the source resolver and the column resolver — the engine only validates the named columns exist, then executes. (The **hint spec** — `metric.role` + `group_by` dimension words — is the exploratory fallback for before the schema is known; migrate off it once you know the column names, because it can be `ambiguous`.)

```python title="query_exact.py"
result = httpx.post(
    f"{base}/v1/query",
    headers=headers,
    json={
        "source_name": "Bookings",
        "metric_column": "measure_total",
        "group_column": "dimension_label",
        "aggregation": "sum",
        "limit": 5,
    },
).json()

print(result["exact_spec"], result["row_count"])
```

Verify: `exact_spec` is `true` and `result` holds your grouped rows. If `exact_spec` were `false`, the request fell through to the hint path — confirm both `source_name` and `metric_column` are set, since the exact path requires both.
{% endstep %}

{% step %}
### Narrow the result with typed filters

Filters are deterministic record predicates over normalized rows, not SQL clauses. Add a `filter` object: a relative `time_filter` window (`last_quarter`, `this_quarter`, `last_month`, `this_month`, `last_year`, `this_year`) and a list of `conditions`. Each condition names a `column` (or a `dimension_hint` when the exact name is unknown), an `op` from the fixed set — `eq`, `in`, `gt`, `gte`, `lt`, `lte`, `is_null`, `is_not_null` — and a `value` (or `values` for `in`).

```python title="query_filtered.py"
result = httpx.post(
    f"{base}/v1/query",
    headers=headers,
    json={
        "source_name": "Bookings",
        "metric_column": "measure_total",
        "group_column": "dimension_label",
        "aggregation": "sum",
        "limit": 5,
        "filter": {
            "time_filter": "last_quarter",
            "conditions": [
                {"column": "status", "op": "in", "values": ["paid", "shipped"]},
                {"column": "amount", "op": "gte", "value": 100},
                {"column": "cancelled_at", "op": "is_null"},
            ],
        },
    },
).json()

print(result["row_count"], result["result"])
```

Verify: the request returns `200` and `row_count` reflects the narrowed set. The operator grammar is enforced — `op: "in"` requires `values` (not `value`), `is_null`/`is_not_null` accept neither, and every other op requires `value`; a malformed condition is rejected with a `422` before execution.
{% endstep %}

{% step %}
### Read the audit fields

Every governed result carries the proof of what ran. Read `validated`, `plan_hash`, and `schema_revision` from the response — identical intent over the same schema revision produces an identical `plan_hash` every time, which is what makes the number replayable and auditable.

```python title="read_audit.py"
print("validated:", result["validated"])
print("plan_hash:", result["plan_hash"])
print("schema_revision:", result["schema_revision"])
print("decision_path:", result["decision_path"])
```

Verify: `validated` is `true`, `plan_hash` is a stable hex string, and `schema_revision` is populated. Run the same request again — `plan_hash` must be identical. If it changed, the underlying schema changed (a new `schema_revision`); re-resolve before comparing numbers across runs.
{% endstep %}
{% endstepper %}

**Expected result**: `POST /v1/query` returns `200` with `exact_spec: true`, `validated: true`, your grouped rows under `result`, a stable `plan_hash`, and a populated `schema_revision`. Re-running the identical request yields the same `plan_hash` — a deterministic, auditable answer over governed data.

## Troubleshooting

{% hint style="warning" %}
- **`clarification_required: true` from `/v1/resolve`** — the planner could not confidently choose a column or source. Inspect `candidates` (ranked, with `confidence` and `score_components`) and re-resolve with a more specific `metric.hint`, a `preferred_source`, or `reject_on_ambiguity: true` to fail instead of guess.
- **`ambiguous: true` from `/v1/query`** — you used the hint spec and multiple columns matched the role. Switch to the exact spec by passing `source_name` + `metric_column` from the resolved plan or the schema.
- **`422` on a filter condition** — the operator grammar was violated. Use `values` (not `value`) with `op: "in"`, omit both with `is_null`/`is_not_null`, and supply `value` for every comparison op.
- **`plan_hash` differs across runs** — the schema changed. Check `schema_revision`; the hash is bound to the revision by design.

See [API errors](../api/errors.md) for the full error envelope.
{% endhint %}

## Next

{% content-ref url="../concepts/governed-data.md" %}
[governed-data.md](../concepts/governed-data.md)
{% endcontent-ref %}

{% content-ref url="../api/reference.md" %}
[reference.md](../api/reference.md)
{% endcontent-ref %}
