# Table of contents

* [What Algenta is](overview.md)

## Getting Started

* [Install](install.md)
* [Quickstart](quickstart.md)
* [Try it without a key](playground.md)
* [Core concepts](concepts.md)
* [Authentication & API keys](authentication.md)

## Engine runtime

* [Verify the bundled engine](engine/bundled-runtime.md)
* [Engine health & verification](engine/health.md)
* [Engine catalog](engine/catalog.md)
* [Runtime libraries](engine/runtime-libraries.md)
* [Runtime library catalog](engine/runtime-library-catalog.md)
* [Kernel inventory](engine/kernel-inventory.md)
* [Declared capabilities](engine/capabilities.md)
* [Batched and chained execution](engine/coarse-execution.md)
* [Reproducibility](engine/reproducibility.md)

## GPU & LLM inference

* [Metal LLM decode](engine/qwen3-metal-decode.md)
* [Model support matrix](engine/model-support-matrix.md)
* [GPU support](engine/gpu-support.md)

## Compute & kernel primitives

* [Data integrity and encoding](engine/data-integrity-and-encoding.md)
* [Compression kernels](engine/compression-kernels.md)
* [Tensor buffer primitives](engine/tensorx-kernels.md)
* [Normalization kernels](engine/normalization-kernels.md)
* [Attention kernels](engine/attention-kernels.md)
* [MLP block kernels](engine/mlp-block-kernels.md)
* [GEMM kernels](engine/gemm-kernels.md)
* [GPU acceleration kernels](engine/gpu-acceleration-kernels.md)
* [LLM inference kernels](engine/llm-inference-kernels.md)

## Machine learning

* [Time-series model selection](engine/ml-model-selection.md)
* [Statistical model comparison](engine/ml-model-comparison.md)
* [Probability calibration](engine/ml-calibration.md)
* [Dense 2D matrices (Matrix2D)](engine/ml-tensor2d.md)
* [LSTM and GRU cells](engine/ml-sequence-cells.md)
* [LSTM sequence training (BPTT)](engine/ml-sequence-training.md)
* [Bit-exact weight serialization](engine/ml-serialization.md)
* [Gradient-boosted regression trees](engine/ml-gradient-boosting.md)
* [Gaussian mixture models](engine/ml-mixture-models.md)
* [Hidden Markov models](engine/ml-hmm.md)
* [Imbalanced-data resampling](engine/ml-imbalance.md)
* [Model ensembling](engine/ml-ensembles.md)
* [Conformal prediction intervals](engine/ml-conformal.md)
* [Model explainability](engine/ml-explainability.md)
* [Gaussian process regression](engine/ml-gaussian-processes.md)
* [Hyperparameter search schedules](engine/ml-automl.md)
* [Fit/transform pipelines](engine/ml-pipelines.md)
* [Trainable linear models](engine/ml-linear-models.md)
* [Symmetric eigendecomposition and thin SVD](engine/ml-eigendecomposition.md)
* [AR/MA estimation (ARIMA building blocks)](engine/ml-arima.md)
* [Feature hashing (the hashing trick)](engine/ml-feature-hashing.md)
* [Partial least squares regression (PLS1)](engine/ml-pls.md)
* [Trainable SVM classifier (simplified SMO)](engine/ml-svm.md)
* [Batched chain greeks](engine/ml-chain-greeks.md)
* [Classical ML algorithms](engine/ml-classical-algorithms.md)

## Optimization & simulation

* [Optimization & decision programs](engine/optimization.md)
* [Optimization benchmark plane](engine/optimization-model-formulation.md)
* [Routing, scheduling & trade-offs](engine/optimization-heuristics.md)
* [Discrete-event simulation & queueing](engine/discrete-event-simulation.md)
* [Strategy comparison & simulation](engine/strategy-simulation.md)
* [Contest simulation & service timing](engine/contest-strategy.md)
* [Reproducible evolutionary search](engine/reproducible-search.md)
* [Asset degradation state](engine/degradation-state.md)

## Time series & statistics

* [Forecasting and backtesting](engine/forecasting.md)
* [ES-RNN residual correction](engine/ml-esrnn.md)
* [Forecast scoring & Murphy decomposition](engine/forecast-scoring.md)
* [Statistical inference](engine/statistical-inference.md)
* [Causal inference](engine/causal-inference.md)
* [Survival analysis](engine/survival-analysis.md)
* [Evaluation & calibration gates](engine/evaluation-calibration.md)
* [Program execution & scoring](engine/program-execution-scoring.md)

## Data & retrieval

* [Sparse systems & graph analytics](engine/sparse-and-graph.md)
* [Retrieval & ranking](engine/retrieval.md)
* [Data quality & feature hygiene](engine/data-quality.md)
* [Geospatial indexing & joins](engine/geospatial.md)
* [Streaming sketches](engine/streaming-sketches.md)
* [Windowed aggregates](engine/streaming-windows.md)
* [Columnar queries](engine/columnar-queries.md)
* [Spreadsheet formula plane](engine/sheet-formula-plane.md)
* [Text processing kernels](engine/text-processing-kernels.md)
* [Vector ranking kernels](engine/vector-ranking-kernels.md)

## Concepts

* [How the engine works](concepts/engine.md)
* [The governed decision lifecycle](concepts/decision-service.md)
* [Governed data & query](concepts/governed-data.md)
* [The capability plane](concepts/capability-plane.md)
* [Simulation models & distributions](concepts/simulation-models.md)
* [Decision memory](concepts/decision-memory.md)
* [Execution ownership & fail-closed](concepts/execution-ownership.md)
* [Deployment modes & privacy](concepts/deployment-modes.md)

## Guides

* [Make your first query](guides/first-query.md)
* [Group data locally with Query.group_by()](guides/local-query-groupby.md)
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
* [Run local LLM decode](guides/run-qwen3-decode.md)
* [Model-agnostic LLM inference](guides/run-qwen3-family-inference.md)

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

## Microsoft & Azure

* [Algenta for Microsoft Cloud](integrations/microsoft/overview.md)
* [Decision Agent in Copilot & Teams](integrations/microsoft/copilot-teams.md)
* [Excel Decision Add-in](integrations/microsoft/excel.md)
* [Sign in with Microsoft Entra](integrations/microsoft/entra-sso.md)
* [Deploy the decision gateway to your Azure](integrations/azure/gateway.md)

## Identity providers

* [Sign in with a generic OIDC provider](integrations/identity/generic-oidc.md)

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

## Trust & Security

* [Trust overview](trust/overview.md)
* [Governed execution](trust/governed-execution.md)
* [Data boundaries](trust/data-boundaries.md)
* [Audit and evidence](trust/audit-and-evidence.md)
* [Identity and access](trust/identity-and-access.md)
* [Capability status](trust/capability-status.md)
* [Protocol compatibility](trust/protocol-compatibility.md)
* [Architecture and trust boundaries](trust/architecture.md)
* [Evidence walkthrough](trust/evidence-walkthrough.md)
* [Security questionnaire](trust/security-questionnaire.md)
* [Supply chain](trust/supply-chain.md)
* [Threat model](trust/threat-model.md)
* [Support policy](trust/support-policy.md)

## HTTP API

* [API overview](api/overview.md)
* [API endpoint reference](api/reference.md)
* [Streaming (SSE)](api/streaming.md)
* [API explorer (live)](api/explorer.md)
* [Error codes](api/errors.md)
* [API stability](api/stability.md)
* [Execution policy & safety limits](api/rate-limits.md)

## Connectors

* [Connectors overview](connectors/overview.md)
* [Connect a database](connectors/databases.md)
* [Connectors reference](connectors/reference.md)
* [Snowflake](connectors/snowflake.md)
* [BigQuery](connectors/bigquery.md)
* [ClickHouse](connectors/clickhouse.md)
* [PostgreSQL](connectors/postgres.md)
* [Oracle Database](connectors/oracle.md)
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

## Benchmarks

* [Benchmarks](benchmarks/overview.md)
* [Compute kernels](benchmarks/compute-kernels.md)
* [NVIDIA kernel benchmarks](benchmarks/nvidia-kernel-benchmarks.md)
* [NVIDIA LLM throughput](benchmarks/nvidia-llm-throughput.md)
* [NVIDIA LLM serving](benchmarks/nvidia-llm-serving.md)
* [Attention](benchmarks/attention.md)
* [Normalization](benchmarks/normalization.md)
* [Feed-forward](benchmarks/feed-forward.md)
* [Code retrieval quality](benchmarks/code-retrieval.md)
* [Dataframe group-by](benchmarks/dataframe-groupby.md)
* [Sort](benchmarks/sort.md)
* [Top-k selection](benchmarks/top-k.md)
* [Graph betweenness centrality](benchmarks/graph-betweenness.md)
* [Survival analysis](benchmarks/survival-analysis.md)
* [Least-squares accuracy](benchmarks/least-squares-accuracy.md)
* [Forecasting on the joint axis](benchmarks/forecasting-joint-axis.md)
* [FinQA exact execution](benchmarks/finqa-exact-execution.md)
* [LLM inference overview](benchmarks/llm-inference-overview.md)
* [Prefill (token input) throughput](benchmarks/llm-prefill-throughput.md)
* [Decode throughput](benchmarks/decode-throughput.md)
* [Batched decode throughput](benchmarks/batched-decode-throughput.md)
* [LLM tool-calling uplift](benchmarks/llm-tool-calling-uplift.md)

## Help

* [Troubleshooting](troubleshooting.md)
* [Glossary](help/glossary.md)
* [Quick reference](help/quick-reference.md)
* [Using these docs with AI](help/ai-access.md)
* [Changelog](changelog.md)
