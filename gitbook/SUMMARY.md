# Table of contents

* [What Algenta is](overview.md)

## Getting Started

* [Install](install.md)
* [Quickstart](quickstart.md)
* [Try it without a key](playground.md)
* [Core concepts](concepts.md)
* [Authentication & API keys](authentication.md)
* [Log in from the terminal](login.md)

## Run the engine

* [Run the Mojo engine](engine/mojo-sidecar.md)
* [Filtered & selective install](engine/filtered-install.md)
* [Engine health & verification](engine/health.md)
* [Engine catalog](engine/catalog.md)
* [Runtime libraries](engine/runtime-libraries.md)
* [Runtime library catalog](engine/runtime-library-catalog.md)
* [How the engine works](concepts/engine.md)

## Concepts

* [The governed decision lifecycle](concepts/decision-service.md)
* [Governed data & query](concepts/governed-data.md)
* [The capability plane](concepts/capability-plane.md)
* [Simulation models & distributions](concepts/simulation-models.md)
* [Decision memory](concepts/decision-memory.md)
* [Execution ownership & fail-closed](concepts/execution-ownership.md)
* [Deployment modes & privacy](concepts/deployment-modes.md)

## Guides

* [Make your first query](guides/first-query.md)
* [Run a decision](guides/run-a-decision.md)
* [Drive a governed decision](guides/governed-decisions.md)
* [Renewal Capacity Allocation pack](guides/renewal-capacity-allocation.md)
* [Simulate a scenario](guides/simulate.md)
* [Run a what-if sweep](guides/what-if.md)
* [Recommend, score & compare](guides/recommend-and-score.md)
* [Query governed data](guides/governed-query.md)
* [Log decisions & record outcomes](guides/decision-memory.md)
* [Drive decisions through the API](guides/decision-memory-api.md)
* [Configure the execution policy](guides/execution-policy.md)
* [Connect a data source](guides/connect-data.md)
* [Map a dataset instantly](guides/instant-map.md)
* [Route & execute capabilities](guides/capabilities.md)
* [Register capability providers & bindings](guides/capability-bindings.md)
* [Connect an external MCP server](guides/external-mcp.md)
* [Run an agent](guides/agent-runs.md)
* [Run an async job](guides/async-jobs.md)
* [Triage a repository](guides/repository-intelligence.md)
* [Fix a repository](guides/repository-fix.md)
* [Prove a security finding](guides/security-analysis.md)
* [Register a trigger](guides/triggers.md)
* [Webhooks](guides/webhooks.md)
* [Bring your own key (BYOK)](guides/byok.md)
* [Device binding](guides/device-binding.md)
* [Run air-gapped](guides/air-gapped.md)
* [Use Algenta in CI/CD](guides/ci-cd.md)

## LLM API

* [LLM models & providers](llm/models.md)
* [Run chat completions](llm/completions.md)
* [Generate embeddings](llm/embeddings.md)

## SDKs

* [Python SDK](sdk/python.md)
  * [Python client reference](sdk/python/overview.md)
  * [Simulations & queries](sdk/python/simulations-and-queries.md)
  * [Decisions & products](sdk/python/decisions-and-products.md)
  * [Connectors & datasets](sdk/python/connectors-and-data.md)
  * [Repository intelligence](sdk/python/repositories.md)
  * [LLM & embeddings](sdk/python/llm.md)
  * [Agent runs](sdk/python/agent-runs.md)
  * [Jobs, triggers & capabilities](sdk/python/jobs-triggers-capabilities.md)
  * [Account & control plane](sdk/python/account-and-control-plane.md)
* [TypeScript SDK](sdk/typescript.md)
  * [TypeScript client reference](sdk/typescript/overview.md)
  * [Simulations & queries](sdk/typescript/simulations-and-queries.md)
  * [Decisions & products](sdk/typescript/decisions-and-products.md)
  * [LLM & model discovery](sdk/typescript/llm.md)
  * [Connectors & data](sdk/typescript/connectors-and-data.md)
  * [Repository intelligence](sdk/typescript/repositories.md)
  * [Agent runs](sdk/typescript/agent-runs.md)
  * [Jobs, triggers & capabilities](sdk/typescript/jobs-triggers-capabilities.md)
  * [Account & control plane](sdk/typescript/account-and-control-plane.md)
* [MCP server](sdk/mcp.md)
* [Install from the MCP Registry](sdk/mcp-registry.md)
* [Tool discovery](sdk/tool-discovery.md)
* [Testing with Algenta](sdk/testing.md)
* [CLI reference](cli.md)
* [algenta CLI (local)](sdk/algenta-cli.md)

## MCP tools

* [MCP tools overview](mcp-tools/overview.md)
* [Data & ingest tools](mcp-tools/data.md)
* [Connector tools](mcp-tools/connectors.md)
* [Query tools](mcp-tools/query.md)
* [Repository intelligence tools](mcp-tools/repository-intelligence.md)
* [LLM utility tools](mcp-tools/llm.md)
* [Capability plane tools](mcp-tools/capability-plane.md)
* [Decision tools](mcp-tools/decisions.md)
* [Async jobs & triggers tools](mcp-tools/jobs-and-triggers.md)
* [Agent run tools](mcp-tools/agent-runs.md)
* [Control plane tools](mcp-tools/control-plane.md)
* [Account & meta tools](mcp-tools/account-and-meta.md)
* [Runtime library tools](mcp-tools/runtime-libraries.md)

## Microsoft & Azure

* [Algenta for Microsoft Cloud](integrations/microsoft/overview.md)
* [Decision Agent in Copilot & Teams](integrations/microsoft/copilot-teams.md)
* [Excel Decision Add-in](integrations/microsoft/excel.md)
* [Sign in with Microsoft Entra](integrations/microsoft/entra-sso.md)
* [Deploy the decision gateway to your Azure](integrations/azure/gateway.md)

## Deploy & Operate

* [Self-hosting](self-hosting.md)
* [Configuration reference](configuration.md)
* [Monitoring & observability](operate/monitoring.md)
* [Encryption at rest (BYOK)](operate/byok-kms.md)
* [Device key store](operate/device-key-store.md)
* [Audit & tighten egress](operate/privacy-egress.md)
* [Teams & roles (RBAC)](operate/teams-rbac.md)
* [Deployments & nodes](operate/deployments-and-nodes.md)
* [Licensing & editions](licensing.md)
* [Usage & limits](billing.md)

## HTTP API

* [API overview](api/overview.md)
* [API endpoint reference](api/reference.md)
* [Streaming (SSE)](api/streaming.md)
* [API explorer (live)](api/explorer.md)
* [Error codes](api/errors.md)
* [Rate limits & quotas](api/rate-limits.md)

## Connectors

* [Connectors overview](connectors/overview.md)
* [Connect a database](connectors/databases.md)
* [Connectors reference](connectors/reference.md)
* [Snowflake](connectors/snowflake.md)
* [BigQuery](connectors/bigquery.md)
* [ClickHouse](connectors/clickhouse.md)
* [PostgreSQL](connectors/postgres.md)
* [MySQL](connectors/mysql.md)
* [Microsoft SQL Server](connectors/mssql.md)
* [SQLite](connectors/sqlite.md)
* [Amazon Redshift](connectors/redshift.md)
* [Amazon S3](connectors/s3.md)
* [Google Cloud Storage](connectors/gcs.md)
* [Azure Blob Storage](connectors/azure-blob.md)
* [Redis](connectors/redis.md)
* [Neo4j](connectors/neo4j.md)
* [Elasticsearch](connectors/elasticsearch.md)
* [Files & uploads](connectors/files.md)
* [Code repositories](connectors/code-repositories.md)
* [REST API](connectors/rest-api.md)

## Help

* [Troubleshooting](troubleshooting.md)
* [Glossary](help/glossary.md)
* [Quick reference](help/quick-reference.md)
* [Using these docs with AI](help/ai-access.md)
* [Changelog](changelog.md)
