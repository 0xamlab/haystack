---
sidebar_position: 5
---

# Power Automate

Use the Codna custom connector in Microsoft Power Automate flows.

## Setup

1. Download the connector definition: [`examples/power-automate/connector_definition.json`](https://github.com/decisionengine/decision-engine/tree/main/examples/power-automate/connector_definition.json)
2. Review the local example bundle guide: [`examples/power-automate/README.md`](https://github.com/decisionengine/decision-engine/tree/main/examples/power-automate/README.md)
3. In Power Automate, go to **Data → Custom Connectors → New custom connector → Import an OpenAPI file**
4. Upload the file and configure your API key
5. Start with the read-only actions:
   - **Get Contract**
   - **List Datasets**
   - **Get Dataset Summary**
   - **Query Dataset**
   - **Query Batch**
   - **Query SQL Report**
6. Keep **Run Simulation** for separate decision-analysis flows

## Usage in a flow

1. Add trigger (e.g., "When a form is submitted")
2. Add **Get Contract** to inspect the live machine-readable Codna surface from `GET /v1/meta/contract`
   - Older self-hosted fallback: if that returns `404`, fetch `/openapi.json` and inspect `x-primary-data-query-contract` instead
   - Inspect `primary_data_query_contract.governed_filter_contract` there when the flow must build deterministic exact filters without SQL
3. Add **List Datasets** with `search = orders` and `compact = true`
4. Add **Get Dataset Summary** for the selected dataset
5. Add **Query Batch** for the exact metrics the flow needs
6. Route on the returned results, not on a simulation envelope, unless the flow is explicitly doing decision analysis

Example bundle:

- [`examples/power-automate/connector_definition.json`](https://github.com/decisionengine/decision-engine/tree/main/examples/power-automate/connector_definition.json)
- [`examples/power-automate/README.md`](https://github.com/decisionengine/decision-engine/tree/main/examples/power-automate/README.md)
- [`examples/power-automate/contract_request.json`](https://github.com/decisionengine/decision-engine/tree/main/examples/power-automate/contract_request.json)
- [`examples/power-automate/openapi_contract_request.json`](https://github.com/decisionengine/decision-engine/tree/main/examples/power-automate/openapi_contract_request.json)
- [`examples/power-automate/query_batch_request.json`](https://github.com/decisionengine/decision-engine/tree/main/examples/power-automate/query_batch_request.json)
- [`examples/power-automate/sql_report_request.json`](https://github.com/decisionengine/decision-engine/tree/main/examples/power-automate/sql_report_request.json)

Use `openapi_contract_request.json` when a raw HTTP action in the flow must
recover the same contract from `/openapi.json` on an older self-hosted node
that still returns `404` for `/v1/meta/contract`.
