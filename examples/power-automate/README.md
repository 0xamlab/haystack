# Power Automate — Algenta

Use the Power Automate custom connector to call Algenta's hosted data, query,
and simulation surfaces from Microsoft flows.

- Cloud Managed: `https://api.algenta.ai`
- `self_hosted` and `air_gapped`: replace the hosted base URL with your self-hosted base URL

Private profiles do not silently fall back to Algenta cloud.

The checked-in JSON templates intentionally use `https://your-algenta-base-url.example`; replace it with Cloud Managed `https://api.algenta.ai` or your self-hosted base URL before import.

## Files

- `connector_definition.json` — importable custom connector definition with the
  primary governed data/query actions and the machine-readable contract action
- `contract_request.json` — request spec for `GET /v1/meta/contract`
- `openapi_contract_request.json` — compatibility request spec for `GET /openapi.json` when older self-hosted nodes still return `404` for `/v1/meta/contract`
- `query_batch_request.json` — request body for `POST /v1/query/batch`
- `sql_report_request.json` — request body for `POST /v1/query/sql-report`

## Quick Setup

1. In Power Automate, go to **Data -> Custom Connectors -> New custom connector
   -> Import an OpenAPI file**
2. Upload `connector_definition.json`
3. Configure `Authorization: Bearer <YOUR_ALGENTA_API_KEY>`
   Use a Cloud Managed key only when the flow targets `https://api.algenta.ai`.
   In `self_hosted` and `air_gapped`, use the API key provisioned by your
   self-hosted operator deployment instead.
4. Start with **Get Contract**
5. Continue with **List Datasets** using `search = orders` and `compact = true`
6. Use **Get Dataset Summary** before **Query Dataset**, **Query Batch**, or
   **Query SQL Report**

If you are mixing the custom connector with raw HTTP actions in a flow, use the
checked-in request specs and bodies in `contract_request.json`,
`openapi_contract_request.json`, `query_batch_request.json`, and
`sql_report_request.json`.

## First flow

The primary Algenta data/query path in Power Automate is:

- `GET /v1/meta/contract`
- `/openapi.json` plus `x-primary-data-query-contract` as the fallback on older self-hosted nodes that still return `404` there
- `GET /v1/data`
- `GET /v1/data/{dataset_id}/summary`
- `POST /v1/query` or `POST /v1/query/batch`
- `POST /v1/query/sql-report` only for wide read-only rowsets

Keep `POST /v1/simulate` as a separate decision-analysis lane, not the default
dataset-query path.

## Notes

- Use **Get Contract** when the flow needs the live discovery/query contract
  from the running service.
- Use `openapi_contract_request.json` when a raw HTTP step must recover the
  same contract from `/openapi.json` on older self-hosted nodes that still
  return `404` for `/v1/meta/contract`.
- Use **Query Batch** when one flow step needs several governed exact metrics.
- Use **Query SQL Report** only when the flow needs a wide read-only rowset over
  already authorized datasets.
- Use `contract_request.json`, `query_batch_request.json`, and
  `sql_report_request.json` when you want copy-pasteable HTTP request payloads
  alongside the custom connector.
- Revoke the Algenta API key if the connector should lose access entirely.
