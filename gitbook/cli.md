---
icon: terminal
description: Install and use the supported Algenta command-line surfaces without managing a separate compute runtime.
---

# Command-line interfaces

Algenta has two command-line surfaces with different ownership boundaries:

| Command | Installed by | Purpose |
| --- | --- | --- |
| `de` | The one-line self-hosted installer | Operate the installed Algenta API: health, keys, data, decisions, agents, repositories, and deployment policy. |
| `algenta` | `pip install algenta` | Run the automatically installed local native runtime and local data helpers. |

`algenta-sdk` is the typed Python HTTP client. It does **not** install either CLI.

## Self-hosted control plane: `de`

The [self-hosted installer](install.md#self-hosted-service) creates
`$HOME/.algenta/bin/de` and links it at `$HOME/.local/bin/de`. The wrapper runs
the control-plane command in the already installed official API container. It
does not install another engine, Python environment, or runtime process.

```bash
curl -sSL https://algenta.ai/install.sh | bash
export PATH="$HOME/.local/bin:$PATH"
export ALGENTA_API_KEY='<bootstrap or replacement key>'

de version
de health
de contract
```

If `ALGENTA_DIR` or `ALGENTA_BIN_DIR` was set during installation, use the same
value when invoking the wrapper. A pre-existing non-symlink file named `de` is
never overwritten; the installer prints the exact wrapper path instead.

### Configuration

The wrapper forwards `ALGENTA_API_KEY` (or legacy `DE_API_KEY`) to the local API
container and targets its loopback API. Secrets remain in the caller's process
environment; they are not placed in command arguments or written by the
wrapper.

For machine-readable output, append `--format json` to commands that expose a
format option.

```bash
de account me --format json
de data list --format json
de account limits --format json
```

Common command groups include:

| Group | Examples |
| --- | --- |
| API and identity | `health`, `contract`, `account`, `keys`, `devices` |
| Data | `data`, `connectors`, `sources`, `query` |
| Decisions | `simulate`, `recommend`, `score`, `batch`, `compare`, `decisions` |
| Agents and jobs | `agent-runs`, `jobs`, `triggers` |
| Repository intelligence | `repos`, `repo` |
| Operations | `deployments`, `execution-policy`, `runtime` |

Use `de` with no arguments to print the command groups and accepted flags from
the installed version. Invalid input and API failures return a non-zero exit
code.

<details>
<summary>Complete command index</summary>

```text
de account distributions
de account limits
de account me
de account templates
de account update
de account usage
de agent-runs approve
de agent-runs cancel
de agent-runs checkpoints
de agent-runs create
de agent-runs events
de agent-runs get
de agent-runs list
de agent-runs mission-events
de agent-runs query-checkpoints
de agent-runs query-mission-events
de agent-runs query-telemetry
de agent-runs resume
de agent-runs telemetry
de benchmark
de billing checkout
de billing info
de billing portal
de capabilities bindings
de capabilities execute
de capabilities list
de capabilities provider
de capabilities providers
de capabilities route
de config set-key
de connectors browse
de connectors create
de connectors delete
de connectors get
de connectors list
de connectors preview-browse
de connectors preview-test
de connectors test
de connectors update
de contract
de credits refresh
de data connect
de data disconnect
de data inspect
de data list
de data query-batch
de data refresh
de data sql-report
de data summary
de decision batch
de decision compare
de decision plan
de decision score
de decisions delete
de decisions execute
de decisions get
de decisions list
de decisions log
de decisions outcome
de deployments cost
de deployments create
de deployments delete
de deployments get
de deployments regions
de devices list
de devices revoke
de execution-policy get
de execution-policy snapshots
de execution-policy update
de health
de job cancel
de job list
de job result
de job status
de job submit
de job wait
de keys create
de keys list
de keys revoke
de llm chat
de llm count-tokens
de llm embedding-similarity
de llm embeddings
de llm models
de llm rerank
de llm resolve-artifact
de llm responses
de llm tokenize
de product agent-run
de product decision
de product forecast
de product optimize
de product retrieve
de recommend examples
de repositories apply
de repositories capabilities
de repositories decision-plan
de repositories get-snapshot
de repositories graph-query
de repositories simulate
de repositories snapshot
de repositories triage
de simulate examples
de team audit-artifacts
de team audit-logs
de team invite
de team list
de team remove
de team update-role
de template get
de template list
de template run
de triggers delete
de triggers fire
de triggers list
de triggers pause
de triggers register
de triggers resume
de version
de webhook test
```

</details>

{% hint style="warning" %}
`de` is currently part of the self-hosted installation, not a PyPI console
script. Do not use `pip install algenta-sdk` as a CLI installation command.
{% endhint %}

## Local native runtime: `algenta`

On supported macOS and Linux platforms, one install resolves both the Python
facade and its matching native runtime wheel:

```bash
python3.14 -m venv .venv
source .venv/bin/activate
pip install algenta

algenta version
algenta runtime doctor
```

Users do not install Mojo, launch a daemon, configure a socket, or install the
native artifact separately. The package verifies the platform wheel and signed
manifest before execution and fails closed if they do not match.

### Runtime catalog

```bash
algenta runtime modules
algenta runtime functions vector_kernels.dot
algenta runtime execute vector_kernels.dot dot64_f32 \
  --args-json '{"a":[1,2,6],"b":[3,2,1]}'
```

The execute command returns JSON. A successful response includes
`"engine_used":"mojo"`; runtime or argument failures return non-zero.

### Native simulation and benchmark

```bash
algenta simulate
algenta benchmark
```

`simulate` executes a 10,000-scenario Monte Carlo in the bundled native runtime.
`benchmark` reports cold startup separately from ten warm native executions.
Neither command uses a Python compute fallback or prints a synthetic speedup.

### Local data helpers

```bash
algenta import orders.csv --name orders
algenta map orders.csv
algenta query "revenue by region" orders.csv
algenta demo
```

Run `algenta` with no arguments for the installed command summary.

## MCP bridge

Install the MCP client separately only when an editor or agent host needs it:

```bash
pipx install algenta-mcp
algenta-mcp
```

The MCP package is an authenticated client of hosted or self-hosted Algenta. It
does not require users to start a local compute service. See [MCP server](sdk/mcp.md).
