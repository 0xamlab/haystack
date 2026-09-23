# algenta

`algenta` is the public Python facade and CLI for Algenta's local native runtime.
The matching platform runtime is installed automatically as a required
dependency. Users do not install Mojo, compile binaries, launch a daemon, or
configure a side process.

For the typed HTTP-only client, use
[`algenta-sdk`](https://pypi.org/project/algenta-sdk/) instead.

## Install

```bash
python3.14 -m venv .venv
source .venv/bin/activate
pip install algenta
```

Supported release targets:

- macOS Apple Silicon
- Linux x86-64
- Python 3.14

Package resolution fails on an unsupported platform instead of installing a
runtime that cannot execute.

## Verify

```bash
algenta version
algenta runtime doctor
algenta simulate
algenta benchmark
```

`benchmark` reports cold startup separately from warm native executions. It
does not use a Python compute fallback or print a synthetic speedup.

## Runtime libraries

The installed contract contains 635 modules and 5,983 callable functions.
Discover and execute them without starting another service:

```bash
algenta runtime modules
algenta runtime functions vector_kernels.dot
algenta runtime execute vector_kernels.dot dot64_f32 \
  --args-json '{"a":[1,2,6],"b":[3,2,1]}'
```

The same surface is available from Python:

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

print(runtime.health())
print(runtime.list_functions("vector_kernels.dot"))

result = runtime.execute(
    "vector_kernels.dot",
    "dot64_f32",
    {"a": [1, 2, 6], "b": [3, 2, 1]},
)

if not result["success"]:
    raise RuntimeError(result["error"])

print(result["result"])       # 13.0
print(result["latency_ms"])
print(result["engine_used"])  # mojo
```

The runtime validates module names, function names, argument counts, scalar and
list types, and public struct fields before execution.

## Local data helpers

```bash
algenta import orders.csv --name orders
algenta map orders.csv
algenta query "revenue by region" orders.csv
algenta demo
```

These commands are local helpers. The governed hosted or self-hosted data/query
surface is available through API mode.

## API mode

Install the cloud extra when the same facade should call an Algenta deployment:

```bash
pip install "algenta[cloud]"
```

```python
import os

from algenta import Runtime

runtime = Runtime(
    mode="self_hosted",
    api_key=os.environ["ALGENTA_API_KEY"],
    base_url="http://localhost:8000",
)

datasets = runtime.list_datasets(search="orders", compact=True)
print(datasets)
```

Private deployment modes require an explicit base URL and fail closed instead
of silently using Algenta cloud.

### Contract discovery

The facade exports the generated public query contract, so applications can
discover endpoint and filter capabilities without hard-coded paths:

```python
from algenta import PRIMARY_DATA_QUERY_CONTRACT

print(PRIMARY_DATA_QUERY_CONTRACT["api"]["contract_endpoint"])
```

The API publishes its OpenAPI document at `/openapi.json` and identifies the
active query contract with `x-primary-data-query-contract`. The main HTTP
facade methods are `get_contract()`, `list_connectors()`, `connect_data()`,
`get_dataset()`, `get_dataset_summary()`, `refresh_dataset()`,
`delete_dataset()`, `query_batch()`, and `query_sql_report()`. Runtime evidence
is discoverable through `get_runtime_manifest()`, `get_runtime_modules()`,
`get_runtime_benchmarks()`, and `get_runtime_release_validation()`.

`Runtime(mode="api")` targets Algenta cloud. `Runtime(mode="self_hosted")`
requires `base_url` to point at your own service and intentionally fails closed
when that configuration is missing.

## Unified Capability Plane

The same facade routes datasets, skills, MCP tools, and runtime libraries:

```python
route = runtime.route_capabilities(
    {
        "objective": "Investigate the latest checkout incident",
        "kinds": ["dataset", "skill", "mcp_tool", "runtime_library"],
    }
)

capability = runtime.get_capability(
    route.selected_capability_id,
    include_instruction=True,
)
execution = runtime.execute_capability(
    {
        "capability_id": route.selected_capability_id,
        "binding_id": route.selected_binding_id,
        "input": {"objective": "Investigate the latest checkout incident"},
    }
)
providers = runtime.list_capability_providers()
skills = runtime.list_skills()
mcp_providers = runtime.list_mcp_providers()
```

Local runtime execution fails closed for `algenta_managed` capabilities. Use
`Runtime(mode="api")` or `Runtime(mode="self_hosted")` for those routes. Local
adapters registered with `runtime.register_capability_adapter(adapter)` execute
only `client_managed` capabilities. Full route and execution examples are in
[`examples/capability-plane/`](../../examples/capability-plane/) and
[`examples/langgraph/capability_router.py`](../../examples/langgraph/capability_router.py).

## Authentication

`algenta login` registers this device under your free community license (required,
free) and stores API and license credentials only in the operating-system
credential store. If no secure keyring backend is available, storage fails
explicitly; set `ALGENTA_API_KEY` in the process environment instead.

```bash
algenta login
algenta whoami
```

The runtime wheel is verified against its signed manifest and platform tag
before public release execution. Release mode denies unverified overrides and
does not open a TCP listener.

## MCP

The MCP client is a separate, thin package because it connects editors and
agents to hosted or self-hosted Algenta:

```bash
pipx install algenta-mcp
algenta-mcp
```

Or install the optional dependency with this package:

```bash
pip install "algenta[mcp]"
algenta mcp
```

Its runtime tools are `list_runtime_libraries` and `execute_runtime_library`.

## Links

- [Documentation](https://docs.algenta.ai)
- [Python and CLI install guide](https://docs.algenta.ai/install)
- [Python SDK reference](https://docs.algenta.ai/sdk/python)
- [Runtime libraries](https://docs.algenta.ai/engine/runtime-libraries)
- [Source](https://github.com/thyn-ai/algenta)
- [Issues](https://github.com/thyn-ai/algenta/issues)
