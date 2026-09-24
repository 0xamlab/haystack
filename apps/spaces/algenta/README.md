---
title: Algenta
emoji: ⚡
colorFrom: purple
colorTo: blue
sdk: docker
app_port: 7860
pinned: true
license: apache-2.0
short_description: "6,000+ compiled Mojo kernels. Race them against Python."
tags:
  - kernels
  - mojo
  - benchmark
  - llm
  - mcp
  - agents
fullWidth: true
header: mini
thumbnail: https://huggingface.co/spaces/thyn-ai/algenta/resolve/main/social.png
---

# Algenta, live

Compiled [Mojo](https://www.modular.com/mojo) kernels from the
[Kernels Hub](https://huggingface.co/thyn-ai), measured on the machine that serves this page.
Every family is a Mojo shared library loaded in-process through a C ABI — there is no Python
fallback, and `/health` names each library, its sha256 and the toolchain that built it. Every number on it is produced by code at boot or on request:
the opening card is measured before the first visitor arrives, every race prints both
latencies and the version of the library it ran against, and anything that cannot run here
says so with an error code instead of a stored result.

## Tabs

| tab | what runs |
|---|---|
| Try it | The opening card: a two-proportion z-test from `thyn-ai/algenta-stats`, gated against statsmodels, then your own inputs. |
| Playground | Any published function: family, module, function, a form generated from the kernel's own contract, the result and the exact snippet to reproduce it. |
| Races | Seeded workloads, the Hub kernel against the Python library it replaces, under one measurement protocol; the incumbent's version is on every card. |
| LLM kernels | RMSNorm, RoPE and sampling from `thyn-ai/algenta-llm`, checked against torch on the CPU: a parity chip against a stated tolerance with both lanes' provenance, and no timing shown — at these shapes a call is transport around a microsecond kernel. |
| Governed | One governed execution on the hosted API, from recommendation to receipt or denial, with the engine's webhook shown next to it. |
| Ecosystem | The families and the umbrella with live Hub counts, the open-source kernels, the SDK and the MCP registry, every count computed here. |

`?tab=<id>` opens a tab directly; the Permalink row at the bottom of the page holds the link
for the current one.

## How the numbers are made

- Kernels load with `kernels.get_kernel("thyn-ai/algenta-<family>", version=1, backend="cpu",
  trust_remote_code=...)` from a cache baked into the image; the runtime never downloads.
- Every native call goes through one lane: the compiled libraries run one call at a time per
  machine, so two visitors are served in turn and no timing reads a queue as work.
- Races follow the fleet's measurement protocol: a correctness gate before timing, discarded
  warm-ups, interleaved repeats, median with spread, both absolute times and the ratio, the
  machine and the UTC stamp on the card. A noisy run is not recorded.
- `/health` returns the boot snapshot and what the page runs on; `/api/status` the compact
  record other Spaces read, whose `measured_utc` stays null until the opening card has been
  measured under the protocol. `facts.json` holds every count and version the copy quotes.

## Run it yourself

```sh
pip install kernels torch
python -c 'from kernels import get_kernel
k = get_kernel("thyn-ai/algenta-stats", version=1, backend="cpu", trust_remote_code=["thyn-ai/algenta-stats"])
print(k.ab_testing.z_test_proportions(50, 1000, 65, 1000))'
```

Duplicate this Space to run it on your own hardware; the image bakes the kernel cache at build
time and boots in seconds.

## Boundary

Space code is Apache-2.0. The kernels it loads are published under the Algenta Community
License 1.1; commercial plans at [algenta.ai/pricing](https://algenta.ai/pricing). Questions
and results: [Discord](https://discord.gg/w8NDsph9an).
