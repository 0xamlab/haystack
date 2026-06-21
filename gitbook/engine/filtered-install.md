---
icon: sliders
description: Install only the parts of Algenta you need — pick a component profile, compile only the engine modules you use, expose a single edition, or run an engine-free control plane.
---

# Filtered & selective install

Algenta is a large system, but you almost never want all of it. Install **only what your use case needs** — a thin client, a local runtime, or the full engine — and, when you do run the engine, compile **only the modules you use** (a full build is ~17 GB). This page is the map of every "less than everything" choice.

## 1. Pick a component profile

| Profile | Install | What you get | Use when |
| --- | --- | --- | --- |
| **SDK only** | `pip install algenta-sdk` (or `npm install algenta-sdk`) | A typed HTTP client for a running API. No engine, no local compute. | You call a hosted or self-hosted Algenta from your app. |
| **Local runtime** | `pip install algenta-core` | The in-process `Runtime` for local resolve/query flows. Add `[cloud]` for the API transport, `[benchmark]` for numpy, `[all]` for both. | You run deterministic flows locally or drive a remote engine from one object. |
| **MCP server** | `pipx install algenta-mcp` | The MCP bridge for Cursor / Claude Desktop. Ships independently. | You give an AI client engine tools. |
| **Full self-hosted** | `curl -sSL https://algenta.ai/install.sh \| bash` | API + worker + **Mojo engine** + Postgres + Redis + object storage (Docker Compose). | You run the complete decision engine on your own infra. |

{% hint style="info" %}
The extras are additive: `pip install "algenta-core[cloud]"` is the local runtime **plus** the HTTP transport. Only the full self-hosted profile pulls the Mojo engine and the data services.
{% endhint %}

## 2. Compile only the engine modules you need

When you build the engine from source, **`MOJO_RUNTIME_MODULE_FILTER`** selects which runtime-library modules are compiled into the binary. An empty filter builds everything (~17 GB of work); a filter builds a small, fast binary with just your modules.

```bash title="filtered-build.sh"
# build a lean binary with only the modules you actually call
MOJO_RUNTIME_MODULE_FILTER="monte_carlo,distributions,optimization_constrained" make build-mojo
```

Confirm what made it in:

```bash title="check-modules.sh"
curl http://localhost:8000/v1/runtime/manifest    # lists the compiled modules
```

{% hint style="warning" %}
A request for a module that wasn't compiled in fails with **"module not registered"**. If you filter, include every module your workloads use — or rebuild without the filter for the full set.
{% endhint %}

## 3. Expose only one edition

A single engine can present a curated **edition** surface (Codna, Cohenta, …) instead of every tool. Set **`ALGENTA_PRODUCT`** (or send `X-Algenta-Product` per request); the MCP/API tool set is filtered to that edition's allowlist (unknown product → empty set, fail-closed).

```bash title="edition.env"
ALGENTA_PRODUCT=codna     # only this edition's tools are visible
```

## 4. Run only the control plane

A deployment runs in one of two roles via **`ALGENTA_SERVICE_ROLE`**:

| Role | Includes | Excludes | Use for |
| --- | --- | --- | --- |
| `full` (default) | Everything — engine, simulate, agent runs, `/mcp`, the Mojo pool | — | The complete service. |
| `control_plane` | Auth, accounts, teams, billing, credits, metering, devices, licensing | The engine + Mojo entirely | A tiny, engine-free auth/billing tier that scales separately. |

The runtime-library HTTP endpoints (`/v1/libraries*`) are **off by default**; enable them only if you need direct module invocation:

```bash title="optional.env"
ALGENTA_SERVICE_ROLE=control_plane            # engine-free control plane
ALGENTA_RUNTIME_LIBRARY_HTTP_API_ENABLED=1    # expose /v1/libraries* (off by default)
```

{% hint style="success" %}
**Expected result** — you install (and build) only the surface your use case needs: a 5 MB SDK, a local runtime, an engine-free control plane, or a lean engine with just your modules — instead of the full stack.
{% endhint %}

## Next

{% content-ref url="mojo-sidecar.md" %}
[mojo-sidecar.md](mojo-sidecar.md)
{% endcontent-ref %}

{% content-ref url="../self-hosting.md" %}
[self-hosting.md](../self-hosting.md)
{% endcontent-ref %}
