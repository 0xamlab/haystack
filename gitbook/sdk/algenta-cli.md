---
icon: terminal
description: Reference for the algenta CLI — the local-first command that runs demos, imports, mapping, and deterministic queries on your machine, plus the rolling-out login and agent tooling.
---

# algenta CLI reference

`algenta` is the **local-first** command. It runs entirely on your machine — a deterministic runtime demo, CSV import previews, instant schema mapping, and local queries — with no server and no API key. It is the zero-friction way to feel Algenta before you stand up the engine. For the full control-plane surface (keys, connectors, agent runs, repositories, deployments), use the [`de` CLI](../cli.md), which talks to the `/v1` HTTP API.

{% hint style="info" %}
The `algenta` command exists in the source runtime package, but the public PyPI runtime distribution is not live yet. Do not treat the `algenta` or legacy `algenta-core` package names as clean-machine PyPI install paths until the runtime release is published. The account and agent commands (`login`, `whoami`, `runtime doctor`, `mcp`) are rolling out; the local commands below are source-build commands today.
{% endhint %}

## algenta vs de

| | `algenta` | `de` |
| --- | --- | --- |
| Install | Source checkout / future runtime release | `pip install algenta-sdk` |
| Where it runs | locally, in-process | against the `/v1` API (self-hosted or hosted) |
| Needs an API key | no (local commands); `algenta login` for account work | yes |
| Best for | offline previews, the runtime demo, quick local queries | the full platform: keys, data, agents, repositories, control plane |

## Install and check

```bash title="install-algenta.sh"
git clone https://github.com/thyn-ai/algenta.git
cd algenta
python3 -m pip install -e packages/algenta
algenta version
```

`algenta version` prints the installed version and the primary runtime path (`Runtime.resolve()` → `Runtime.query()`), plus the secondary local modes.

## Local commands

These run on your machine and need no key or network.

| Command | What it does |
| --- | --- |
| `algenta demo` | Interactive local runtime demo (register → resolve → verify → query). |
| `algenta demo --list` | List the selectable demo scenarios and exit. |
| `algenta demo --scenario <id>` | Run one named scenario non-interactively. |
| `algenta demo --all --no-interactive` | Run every scenario in sequence, no prompts. |
| `algenta import <file.csv> [--name <n>]` | Branded local import preview for one source. |
| `algenta import a.csv b.csv` | Bundle preview across several sources (finds relationships). |
| `algenta map <file1.csv> [file2.csv ...]` | Instant local schema mapping and join-key discovery. |
| `algenta query "<text>" <file.csv> [more.csv ...]` | Deterministic local query helper. |
| `algenta simulate` | Run a quick local Monte Carlo simulation. |
| `algenta benchmark` | Show local speedup versus a raw-Python baseline. |
| `algenta upgrade` | Print how to switch to direct API mode. |
| `algenta version` | Show version and capabilities. |

### `algenta demo`

The built-in scenario keys are `product_line`, `region`, `canada_filter`, and `guardrail`.

{% code title="algenta-demo.sh" %}
```bash
algenta demo                                  # interactive picker (in a TTY)
algenta demo --list                           # list scenarios and exit
algenta demo --scenario region --no-interactive
algenta demo --all --no-interactive           # run them all
```
{% endcode %}

### `algenta import`

`--name` is only valid when importing a single source. Import ends by printing a copy-pasteable `Runtime()` snippet.

{% code title="algenta-import.sh" %}
```bash
algenta import orders.csv --name orders
algenta import orders.csv financial.csv ratings.csv
```
{% endcode %}

### `algenta map`

{% code title="algenta-map.sh" %}
```bash
algenta map sales.csv orders.csv
```
{% endcode %}

Add a second source to surface cross-table join keys and confidence scores.

### `algenta query`

The query text comes first, then one or more files.

{% code title="algenta-query.sh" %}
```bash
algenta query "total revenue by customer" sales.csv
algenta query "top 10 orders by amount" orders.csv
```
{% endcode %}

### `algenta simulate` and `algenta benchmark`

{% code title="algenta-simulate.sh" %}
```bash
algenta simulate     # quick local simulation (revenue=100,000 cost=70,000 runs=10,000)
algenta benchmark    # local speedup vs a Python baseline
```
{% endcode %}

### `algenta upgrade`

Prints the exact steps to move from the in-process runtime to direct API mode — the base URL to set, where to get a key, and the before/after `Runtime(mode="api", ...)` code.

{% code title="algenta-upgrade.sh" %}
```bash
algenta upgrade
```
{% endcode %}

## Account and agent commands (rolling out)

These connect the local CLI to your account and to agent tooling. They are shipping incrementally; until they land on your install, use the [`de` CLI](../cli.md) and [API-key authentication](../authentication.md).

| Command | What it does |
| --- | --- |
| `algenta login` | Browser device login — approve a code at `accounts.thyn.ai`, then the CLI stores a machine-scoped key. |
| `algenta login --no-browser` | Print the verification URL and code instead of opening a browser (headless / SSH). |
| `algenta whoami` | Confirm you are signed in (prints the stored key's prefix). |
| `algenta runtime doctor` | Diagnose the bundled verified native runtime. |
| `algenta mcp` | Start the Algenta MCP server for local AI clients. |

{% code title="algenta-login.sh" %}
```bash
algenta login
algenta login --no-browser
algenta whoami
```
{% endcode %}

See [Log in from the terminal](../login.md) for the full device-login walkthrough and [Install from the MCP Registry](mcp-registry.md) for connecting the MCP server to Cursor, Claude, and Codex.

## Related

{% content-ref url="../cli.md" %}
[cli.md](../cli.md)
{% endcontent-ref %}

{% content-ref url="../login.md" %}
[login.md](../login.md)
{% endcontent-ref %}

{% content-ref url="mcp-registry.md" %}
[mcp-registry.md](mcp-registry.md)
{% endcontent-ref %}
