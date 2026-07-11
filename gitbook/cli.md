---
icon: terminal
description: The complete de CLI reference — every command group, subcommand, flag, and the /v1 endpoint it calls, with a copy-ready titled example for each.
---

# CLI reference

The `de` CLI puts the Algenta HTTP platform behind one verb. From a terminal you register a device, manage API keys and execution policy, connect data and run governed queries, route capabilities, score decisions, drive agent runs and async jobs, triage and fix repositories, and manage billing and your team. Commands wrap the same `/v1` HTTP surface the SDKs use, so anything here can be reproduced with `curl` or a published client.

{% hint style="info" %}
Every command maps one-to-one to a `/v1` endpoint. If you can do it in the CLI, you can do it from any SDK or from raw `curl` — the CLI invents no behavior of its own.
{% endhint %}

## Invocation

Install the SDK and the `de` command is on your PATH.

```bash title="install-de.sh"
# Python (ships the de CLI)
pip install algenta-sdk

de version
de health
de contract
```

The TypeScript SDK is available as `algenta-sdk` on npm for JavaScript and TypeScript API clients. It does not install the `de` CLI; use the Python `algenta-sdk` package when you need the terminal command.

Running `de` with no arguments prints the full usage banner.

{% hint style="info" %}
`de` is the supported control-plane CLI documented here.
{% endhint %}

## Configuration and environment

The CLI reads credentials and the API origin from environment variables first, then from `~/.de/config.json`. The config directory is overridable with `DE_CONFIG_DIR`.

| Variable | Purpose |
| --- | --- |
| `ALGENTA_API_KEY` | API key (preferred). Falls back to `DE_API_KEY`. |
| `DE_API_KEY` | Legacy API key name. Still honored. |
| `ALGENTA_BASE_URL` | API origin. Also accepts `DE_BASE_URL` and `ALGENTA_API_URL`. |
| `ALGENTA_APP_BASE_URL` | Dashboard/app origin. Also `APP_BASE_URL`, `DE_APP_BASE_URL`. |
| `DE_CONFIG_DIR` | Override the config directory (default `~/.de`). |

```bash title="set-env.sh"
export ALGENTA_BASE_URL="https://api.algenta.ai"
export ALGENTA_API_KEY="de_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

de account me
```

{% hint style="success" %}
Keys saved through the CLI are stored securely: it uses the OS keyring when available, falls back to a Fernet-encrypted file (`~/.de/secrets.bin`), and only stores plaintext in `config.json` as a last resort.
{% endhint %}

{% hint style="warning" %}
Private profiles (`self_hosted`, `air_gapped`) fail closed. The CLI will not silently fall back to the Algenta cloud — set an explicit `ALGENTA_BASE_URL` (or save `base_url` in config). Credential examples that reference `app.algenta.ai` are the Cloud Managed path; on a private profile, use the API key your operator deployment provisions.
{% endhint %}

### Output format

Nearly every read command accepts `--format table` (default) or `--format json`. Use `json` for scripting.

```bash title="output-format.sh"
de keys list --format json | jq '.api_keys[].key_prefix'
de data list --format json
```

### `request.json` file arguments

Commands that create or update resources take a path to a JSON file rather than inline flags. The file is the request body sent to the endpoint.

```bash title="request-file.sh"
cat > connect.json <<'JSON'
{
  "connection_type": "file_upload",
  "dataset_name": "Sales",
  "csv": "amount\n10\n20\n"
}
JSON

de data connect --request connect.json
```

---

## Authentication and identity

### Login and device registration

`de login` registers this machine, issues a device license (JWT), and stores it locally. `POST /v1/device/register`.

{% tabs %}
{% tab title="Interactive" %}
```bash title="de-login.sh"
de login                  # prompts for the API key
de logout                 # remove the stored device license
de license                # show device license status
de license status         # explicit alias
```
{% endtab %}

{% tab title="Argument (CI-safe)" %}
```bash title="de-login-arg.sh"
de login $ALGENTA_API_KEY
```
{% endtab %}

{% tab title="Environment" %}
```bash title="de-login-env.sh"
ALGENTA_API_KEY=$ALGENTA_API_KEY de login
```
{% endtab %}
{% endtabs %}

`de license` prints the device id, plan, device limit, permitted modules, license source, and expiry.

### `config set-key`

Save an API key (and optionally a base URL) to the secure CLI config store.

```bash title="de-config-set-key.sh"
de config set-key $ALGENTA_API_KEY
de config set-key $ALGENTA_API_KEY https://api.algenta.ai
```

### `keys` — API key lifecycle

| Command | Endpoint |
| --- | --- |
| `de keys list` | `GET /v1/api-keys` |
| `de keys create "<label>"` | `POST /v1/api-keys` (`--expires-at`, `--device-limit`) |
| `de keys revoke $KEY_ID` | `DELETE /v1/api-keys/{key_id}` |

```bash title="de-keys.sh"
de keys list
de keys create "Mission Key" --device-limit 5 --expires-at 2027-01-01T00:00:00Z
de keys revoke $KEY_ID
```

{% hint style="danger" %}
The raw key is shown only once, at creation. Capture it then — there is no way to retrieve it afterward.

```bash title="de-keys-create-json.sh"
de keys create "CI runner" --format json
# {"id": "...", "label": "CI runner", "key_prefix": "de_live_ab", "raw_key": "de_live_..."}
```
{% endhint %}

### `account` — identity, usage, and limits

| Command | Endpoint |
| --- | --- |
| `de account me` | `GET /v1/me` |
| `de account update <request.json>` | `PATCH /v1/me` |
| `de account usage` | `GET /v1/usage` |
| `de account limits` | `GET /v1/limits` |
| `de account distributions` | `GET /v1/distributions` |
| `de account templates` | `GET /v1/templates` |

```bash title="de-account.sh"
de account me
de account usage --format json
echo '{"org_name": "Acme Decisioning"}' > rename.json
de account update rename.json
```

### `devices` — registered machines

| Command | Endpoint |
| --- | --- |
| `de devices list` | `GET /v1/device/list` |
| `de devices revoke $REGISTRATION_ID` | `DELETE /v1/device/{registration_id}` |

```bash title="de-devices.sh"
de devices list
de devices revoke $REGISTRATION_ID
```

### `execution-policy` — governance thresholds

| Command | Endpoint |
| --- | --- |
| `de execution-policy get` | `GET /v1/execution/policy` |
| `de execution-policy snapshots` | `GET /v1/execution/policy/snapshots` |
| `de execution-policy update <request.json>` | `PATCH /v1/execution/policy` |

```bash title="de-execution-policy.sh"
de execution-policy get
cat > policy.json <<'JSON'
{"min_confidence": 0.8, "risk_floor": 0.05, "require_calibration": true}
JSON
de execution-policy update policy.json
```

---

## Data and query

### `data` — datasets

| Command | Endpoint | Notes |
| --- | --- | --- |
| `de data connect --request <file>` | `POST /v1/data/connect` | Connect a dataset. |
| `de data list` | `GET /v1/data` | `--search`, `--status`, `--source-name`, `--page`, `--limit`, `--compact`. |
| `de data summary $DATASET_ID` | low-token summary | |
| `de data inspect $DATASET_ID` | one-dataset detail | |
| `de data query-batch <request.json>` | governed exact-query batch | |
| `de data sql-report <request.json>` | read-only SQL report | |
| `de data refresh $DATASET_ID` | refresh schema/contents | |
| `de data disconnect $DATASET_ID` | delete; `--yes` to skip prompt | |

```bash title="de-data.sh"
de data list --search orders --compact --limit 5
de data summary orders_facts
de data inspect orders_facts --format json
de data query-batch batch_request.json
de data sql-report sql_report_request.json
de data refresh orders_facts
de data disconnect orders_facts --yes
```

### `connectors` — saved and inline connectors

| Command | Endpoint |
| --- | --- |
| `de connectors create <request.json>` | `POST /v1/connectors` |
| `de connectors list` | `GET /v1/connectors` (`--page`, `--limit`) |
| `de connectors get $CONNECTOR_ID` | `GET /v1/connectors/{id}` |
| `de connectors update $CONNECTOR_ID <request.json>` | `PATCH /v1/connectors/{id}` |
| `de connectors test $CONNECTOR_ID` | `POST /v1/connectors/{id}/test` |
| `de connectors browse $CONNECTOR_ID` | `GET /v1/connectors/{id}/browse` |
| `de connectors preview-test <request.json>` | `POST /v1/connectors/test` (inline, unsaved) |
| `de connectors preview-browse <request.json>` | `POST /v1/connectors/browse` (inline, unsaved) |
| `de connectors delete $CONNECTOR_ID` | `DELETE /v1/connectors/{id}` |

```bash title="de-connectors.sh"
de connectors create connector.json
de connectors list --limit 25 --format json
de connectors get $CONNECTOR_ID
de connectors update $CONNECTOR_ID connector_update.json
de connectors test $CONNECTOR_ID
de connectors browse $CONNECTOR_ID
de connectors preview-test inline_connector.json
de connectors preview-browse inline_connector.json
de connectors delete $CONNECTOR_ID
```

### `capabilities` — unified capability plane

| Command | Endpoint |
| --- | --- |
| `de capabilities providers` | `GET /v1/capability-providers` |
| `de capabilities provider $PROVIDER_ID` | `GET /v1/capability-providers/{id}` |
| `de capabilities bindings` | bindings list (`--provider-id`, `--scope`) |
| `de capabilities list` | unified capabilities (`--kind`, `--provider-id`, `--binding-id`) |
| `de capabilities route <request.json>` | `POST /v1/capabilities/route` |
| `de capabilities execute <request.json>` | `POST /v1/capabilities/execute` |

```bash title="de-capabilities.sh"
de capabilities providers
de capabilities provider $PROVIDER_ID
de capabilities bindings --scope organization
de capabilities list --kind retrieval,forecast --format json
de capabilities route route_objective.json
de capabilities execute selected_capability.json
```

{% hint style="info" %}
`--provider-id`, `--binding-id`, and `--kind` accept comma-separated values. `--scope` is one of `user`, `workspace`, `organization`.
{% endhint %}

---

## Decisions, LLM, and products

### `decision` — structured plans and scoring

| Command | Endpoint |
| --- | --- |
| `de decision plan <request.json>` | `POST /v1/decisions/plan` |
| `de decision score <request.json>` | `POST /v1/score` |
| `de decision batch <request.json>` | `POST /v1/batch` |
| `de decision compare <request.json>` | `POST /v1/compare` |

```bash title="de-decision.sh"
de decision plan plan_request.json --format json
de decision score score_request.json
de decision batch batch_request.json
de decision compare scenarios.json
```

### `decisions` — decision memory

| Command | Endpoint |
| --- | --- |
| `de decisions log <request.json>` | `POST /v1/decisions` |
| `de decisions list` | `GET /v1/decisions` (`--page`, `--limit`, `--page-size`, `--with-outcome-only`) |
| `de decisions get $DECISION_ID` | `GET /v1/decisions/{id}` |
| `de decisions outcome $DECISION_ID <request.json>` | `PATCH /v1/decisions/{id}/outcome` |
| `de decisions execute $DECISION_ID <request.json>` | `POST /v1/decisions/{id}/execute` |
| `de decisions delete $DECISION_ID` | `DELETE /v1/decisions/{id}` |

```bash title="de-decisions.sh"
de decisions log record.json
de decisions list --with-outcome-only --limit 50
de decisions get $DECISION_ID
de decisions outcome $DECISION_ID actual_outcome.json
de decisions execute $DECISION_ID dispatch.json
de decisions delete $DECISION_ID
```

### `llm` — deterministic utility surface

| Command | Endpoint | Notes |
| --- | --- | --- |
| `de llm models` | `GET /v1/models` | List truthful utility models. |
| `de llm resolve-artifact <request.json>` | `POST /v1/artifacts/resolve` | HF artifact bridge. |
| `de llm tokenize --input "<text>"` | `POST /v1/tokenize` | `--model` (default `text.tokenizer`). |
| `de llm count-tokens --input "<text>"` | `POST /v1/count_tokens` | `--model`. |
| `de llm chat <request.json>` | `POST /v1/chat/completions` | `--stream`. |
| `de llm responses <request.json>` | `POST /v1/responses` | `--stream`. |
| `de llm embeddings <request.json>` | `POST /v1/embeddings` | |
| `de llm embedding-similarity <request.json>` | `POST /v1/embeddings/similarity` | |
| `de llm rerank <request.json>` | `POST /v1/rerank` | |

```bash title="de-llm.sh"
de llm models
de llm tokenize --input "hello world"
de llm count-tokens --input "hello world" --model text.tokenizer --format json
de llm chat chat_request.json --stream
de llm responses responses_request.json --stream
de llm embeddings embeddings_request.json
de llm embedding-similarity similarity_request.json
de llm rerank rerank_request.json
```

{% hint style="info" %}
`--stream` consumes a Server-Sent Events stream (`Accept: text/event-stream`) and renders deltas as they arrive.
{% endhint %}

### `product` — high-level helpers

| Command | Endpoint |
| --- | --- |
| `de product decision <request.json>` | `POST /v1/decision` |
| `de product agent-run <request.json>` | `POST /v1/agent/run` |
| `de product optimize <request.json>` | `POST /v1/optimize` |
| `de product retrieve <request.json>` | `POST /v1/retrieve` |
| `de product forecast <request.json>` | `POST /v1/forecast` |

```bash title="de-product.sh"
de product decision decision.json
de product agent-run agent_task.json
de product optimize optimize.json --format json
de product retrieve retrieve.json
de product forecast forecast.json
```

---

## Agents and jobs

### `agent-runs` — persisted run lifecycle

| Command | Endpoint |
| --- | --- |
| `de agent-runs list` | `GET /v1/agent/runs` |
| `de agent-runs create <request.json>` | `POST /v1/agent/runs` |
| `de agent-runs get $RUN_ID` | `GET /v1/agent/runs/{id}` |
| `de agent-runs events $RUN_ID` | `GET /v1/agent/runs/{id}/events` (`--stream`) |
| `de agent-runs checkpoints $RUN_ID` | `GET /v1/agent/runs/{id}/checkpoints` |
| `de agent-runs query-checkpoints` | `GET /v1/agent/runs/checkpoints` |
| `de agent-runs mission-events $RUN_ID` | `GET /v1/agent/runs/{id}/mission-events` |
| `de agent-runs telemetry $RUN_ID` | `GET /v1/agent/runs/{id}/telemetry` |
| `de agent-runs query-mission-events` | cross-run mission events |
| `de agent-runs query-telemetry` | cross-run telemetry batches |
| `de agent-runs resume $RUN_ID` | `POST /v1/agent/runs/{id}/resume` |
| `de agent-runs cancel $RUN_ID` | `POST /v1/agent/runs/{id}/cancel` |
| `de agent-runs approve $RUN_ID` | `POST /v1/agent/runs/{id}/approve` |

Drive a run through its full lifecycle:

{% stepper %}
{% step %}
### Create the run

```bash title="de-agent-runs-create.sh"
de agent-runs create run_request.json
```
{% endstep %}

{% step %}
### Watch it execute

```bash title="de-agent-runs-watch.sh"
de agent-runs list --status running --limit 25
de agent-runs get $RUN_ID
de agent-runs events $RUN_ID --stream
de agent-runs checkpoints $RUN_ID
```
{% endstep %}

{% step %}
### Release, resume, or cancel

```bash title="de-agent-runs-transition.sh"
de agent-runs approve $RUN_ID   # release a run waiting for approval
de agent-runs resume $RUN_ID
de agent-runs cancel $RUN_ID
```
{% endstep %}
{% endstepper %}

{% expandable title="Shared filters across list and query-* commands" %}
`list` and the `query-*` commands share filters: `--status`, `--request-hash`, `--policy-snapshot-id`, `--schema-snapshot-id`, plus `--run-id`, `--checkpoint-id`, `--event-type`, `--telemetry-kind`, `--module-name` on the relevant variants.
{% endexpandable %}

### `job` — async jobs for large runs

| Command | Endpoint |
| --- | --- |
| `de job submit <request.json>` | `POST /v1/jobs` (`--callback <url>`) |
| `de job list` | `GET /v1/jobs/list` (`--page`, `--limit`, `--status`) |
| `de job status $JOB_ID` | `GET /v1/jobs/{id}` |
| `de job result $JOB_ID` | `GET /v1/jobs/{id}/result` |
| `de job cancel $JOB_ID` | `POST /v1/jobs/{id}/cancel` |
| `de job wait $JOB_ID` | polls `GET /v1/jobs/{id}` (`--timeout`, default 300s) |

```bash title="de-job.sh"
de job submit large.json --callback https://example.com/hooks/de
de job list --status running
de job status $JOB_ID
de job wait $JOB_ID --timeout 600
de job result $JOB_ID --format json
de job cancel $JOB_ID
```

### `triggers` — scheduled and event triggers

| Command | Endpoint |
| --- | --- |
| `de triggers register <request.json>` | `POST /v1/triggers` |
| `de triggers list` | triggers list (`--status`, `--page`, `--limit`) |
| `de triggers fire $TRIGGER_ID` | `POST /v1/triggers/{id}/fire` (`--force`) |
| `de triggers pause $TRIGGER_ID` | `PATCH /v1/triggers/{id}/pause?paused=true` |
| `de triggers resume $TRIGGER_ID` | `PATCH /v1/triggers/{id}/pause?paused=false` |
| `de triggers delete $TRIGGER_ID` | `DELETE /v1/triggers/{id}` |

```bash title="de-triggers.sh"
de triggers register trigger.json
de triggers list --status active
de triggers fire $TRIGGER_ID --force
de triggers pause $TRIGGER_ID
de triggers resume $TRIGGER_ID
de triggers delete $TRIGGER_ID
```

### `webhook` — delivery test

```bash title="de-webhook.sh"
de webhook test https://example.com/hooks/de   # POST /v1/webhooks/test
```

---

## Repositories

The `repositories` group is the code-intelligence and autonomous-fix surface. Most subcommands take a `$REPOSITORY_ID` and a `<request.json>` body.

| Command | Endpoint |
| --- | --- |
| `de repositories capabilities` | `GET /v1/repositories/capabilities` |
| `de repositories snapshot $REPOSITORY_ID <request.json>` | `POST /v1/repositories/{id}/snapshots` |
| `de repositories get-snapshot $REPOSITORY_ID $SNAPSHOT_ID` | `GET /v1/repositories/{id}/snapshots/{snapshot_id}` |
| `de repositories triage $REPOSITORY_ID <request.json>` | `POST /v1/repositories/{id}/triage` |
| `de repositories decision-plan $REPOSITORY_ID <request.json>` | `POST /v1/repositories/{id}/decision-plans` |
| `de repositories graph-query $REPOSITORY_ID <request.json>` | `POST /v1/repositories/{id}/graph-query` |
| `de repositories pipeline $REPOSITORY_ID <request.json>` | `POST /v1/repositories/{id}/pipeline` |
| `de repositories simulate $REPOSITORY_ID <request.json>` | `POST /v1/repositories/{id}/simulate` |
| `de repositories simulate-patch $REPOSITORY_ID <request.json>` | `POST /v1/repositories/{id}/simulate-patch` |
| `de repositories fix $REPOSITORY_ID <request.json>` | pipeline then apply (composite) |
| `de repositories apply $REPOSITORY_ID <request.json>` | `POST /v1/repositories/{id}/apply` |

Work a repository from discovery through a gated apply:

{% stepper %}
{% step %}
### Discover supported languages

```bash title="de-repositories-capabilities.sh"
de repositories capabilities --format json
```
{% endstep %}

{% step %}
### Snapshot, triage, and plan

```bash title="de-repositories-plan.sh"
de repositories snapshot $REPOSITORY_ID snapshot_request.json
de repositories triage $REPOSITORY_ID triage_request.json
de repositories decision-plan $REPOSITORY_ID plan_request.json
```
{% endstep %}

{% step %}
### Inspect change-risk edges

```bash title="de-repositories-graph.sh"
de repositories graph-query $REPOSITORY_ID graph_query.json
```
{% endstep %}

{% step %}
### Simulate, then gate the apply

```bash title="de-repositories-apply.sh"
de repositories simulate-patch $REPOSITORY_ID simulate_patch.json
de repositories apply $REPOSITORY_ID apply_request.json
```
{% endstep %}
{% endstepper %}

`de repositories fix` is a composite: it runs the pipeline (snapshot, plan, simulate) and then applies the result. The request file may carry a `pipeline` block and an `apply` block; the `apply` block selects the output channel:

```json title="fix_request.json"
{
  "pipeline": { "ref": "main", "objective": "fix failing tests" },
  "apply": {
    "mode": "remote_pr",
    "write_permission": true,
    "branch_name": "algenta/fix-flaky-tests",
    "commit_message": "Fix flaky retry test",
    "pull_request_title": "Fix flaky retry test",
    "pull_request_body": "Generated by Algenta repositories fix."
  }
}
```

```bash title="de-repositories-fix.sh"
de repositories fix $REPOSITORY_ID fix_request.json --format json
```

{% hint style="info" %}
`apply` modes range from `patch_only` (emit a `.diff`) through a local branch to a remote pull request. The pipeline must complete through `simulate` before `fix` will apply — the CLI refuses to apply a plan that has no simulation result.
{% endhint %}

---

## Billing, team, and governance

### `billing` — plan and subscription

| Command | Endpoint |
| --- | --- |
| `de billing info` | `GET /v1/billing/info` |
| `de billing checkout [developer\|pro]` | `POST /v1/billing/checkout` |
| `de billing portal` | `POST /v1/billing/portal` |

```bash title="de-billing.sh"
de billing info
de billing checkout developer
de billing portal
```

### `credits` and `metering` — managed-runtime compatibility

These commands expose generic managed-deployment compatibility endpoints. Self-hosted Algenta editions do not use them for billing or enforcement: decisions are unlimited and the private profiles keep execution audit records local.

| Command | Endpoint |
| --- | --- |
| `de credits refresh <request.json>` | `POST /v1/credits/refresh` |
| `de metering ingest <request.json>` | `POST /v1/metering` |

```bash title="de-credits.sh"
de credits refresh credit_batch.json
de metering ingest metering_batch.json
```

### `team` — members and audit

| Command | Endpoint |
| --- | --- |
| `de team list` | `GET /v1/team` |
| `de team invite <email> [role]` | `POST /v1/team/invite` |
| `de team update-role $USER_ID <role>` | `PATCH /v1/team/{user_id}/role` |
| `de team remove $USER_ID` | `DELETE /v1/team/{user_id}` |
| `de team audit-logs` | `GET /v1/audit-logs` |
| `de team audit-artifacts` | `GET /v1/audit-logs/artifacts` |

```bash title="de-team.sh"
de team list
de team invite teammate@example.com admin
de team update-role $USER_ID member
de team remove $USER_ID
de team audit-logs --action api_key.create --limit 50
de team audit-artifacts --resource-type api_key
```

{% hint style="info" %}
`audit-logs` and `audit-artifacts` share filters: `--actor-email`, `--action`, `--resource-type`, `--result`, `--policy-snapshot-id`, `--schema-snapshot-id`, `--manifest-version`, `--request-hash` (plus `--content-hash` on artifacts).
{% endhint %}

---

## Runtime, deployments, and meta

### `deployments` — managed regions and provisioning

| Command | Endpoint |
| --- | --- |
| `de deployments regions` | `GET /v1/deployments/regions` |
| `de deployments get` | `GET /v1/deployments` |
| `de deployments create <request.json>` | `POST /v1/deployments` |
| `de deployments cost $DEPLOYMENT_ID` | `GET /v1/deployments/{id}/cost` |
| `de deployments delete $DEPLOYMENT_ID` | `DELETE /v1/deployments/{id}` |

```bash title="de-deployments.sh"
de deployments regions --format json
de deployments create deployment.json
de deployments get
de deployments cost $DEPLOYMENT_ID
de deployments delete $DEPLOYMENT_ID
```

### Meta and quick runs

| Command | Endpoint / action |
| --- | --- |
| `de health` | `GET /v1/health` |
| `de contract` | `GET /v1/meta/contract` (machine-readable platform contract) |
| `de version` | `GET /v1/version` (API and engine versions) |
| `de benchmark` | local Mojo-vs-Python benchmark summary |
| `de simulate <file.json>` | `POST /v1/simulate` (`--format`) |
| `de recommend <file.json>` | `POST /v1/recommend` |

```bash title="de-meta.sh"
de health
de contract --format json
de version
de benchmark
de simulate examples/sample.json
de recommend examples/compare.json
```

### `template` — ready-to-run simulations

| Command | Endpoint |
| --- | --- |
| `de template list` | `GET /v1/simulate/templates` |
| `de template run <id>` | `POST /v1/templates/{id}/run` (`--runs`) |
| `de template get <id>` | `GET /v1/simulate/templates/{id}` |

```bash title="de-template.sh"
de template list
de template run finance_npv --runs 100000
de template get finance_npv
```

---

## Scripting patterns

The CLI is built for pipelines. `--format json` plus `jq` gives clean machine output, and exit codes are non-zero on API errors.

```bash title="ci-patterns.sh"
# Capture a new key prefix
PREFIX=$(de keys create "Batch worker" --format json | jq -r '.key_prefix')

# Submit a job and block until it finishes, then pull the result
JOB=$(de job submit large.json --format json | jq -r '.job_id')
de job wait "$JOB" --timeout 900
de job result "$JOB" --format json > result.json

# Fail a CI step if the platform is unhealthy
de health --format json | jq -e '.status == "ok"' > /dev/null
```

Because each command maps one-to-one to a `/v1` endpoint, you can always reproduce a step directly:

```bash title="curl-equivalent.sh"
curl -s "$ALGENTA_BASE_URL/v1/me" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" | jq
```

---

## Related pages

{% content-ref url="authentication.md" %}
[authentication.md](authentication.md)
{% endcontent-ref %}

{% content-ref url="api/reference.md" %}
[api/reference.md](api/reference.md)
{% endcontent-ref %}

{% content-ref url="troubleshooting.md" %}
[troubleshooting.md](troubleshooting.md)
{% endcontent-ref %}
