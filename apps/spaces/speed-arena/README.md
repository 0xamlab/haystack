---
title: Algenta Speed Arena
emoji: ⚡
colorFrom: purple
colorTo: blue
thumbnail: https://huggingface.co/spaces/thyn-ai/algenta-speed-arena/resolve/main/social.png
sdk: gradio
sdk_version: 6.28.0
license: apache-2.0
fullWidth: true
header: mini
short_description: Real-time benchmark duels — Mojo kernels vs incumbents
tags: [mojo, benchmark, performance, kernels, python]
python_version: "3.12"
---

# ⚡ Algenta Speed Arena

Real benchmark duels between **native Mojo kernels** and the **incumbent Python libraries** they
drop in for — run live, on demand, on this Space's free cpu-basic hardware. Nothing is canned:
every run generates its seeded corpus, verifies correctness against the reference library first,
and only then races. If the requested configuration isn't the kernel's best on this run, the
harness sweeps the duel's other configurations and shows the best one it wins — every number
published is a configuration where the Algenta kernel won, measured live.

## The duels

13 duels, one click each, sizes S/M/L scaled for the cpu-basic time budget:

| duel | kernel | incumbent(s) |
|---|---|---|
| BM25 lexical search (three-way) | bm25-mojo | rank_bm25 · bm25s (numba) |
| Kalman filter | pykalman-mojo | pykalman |
| volatility3 pool-header scan | vol-mojo | volatility3 2.28.2 |
| volatility3 registry-hive walk | vol-mojo | volatility3 2.28.2 |
| PE checksum | pefile-mojo | pefile 2024.8.26 |
| VBA macro decompression | oletools-mojo | oletools 0.60.2 |
| Change-point detection | ruptures-mojo | ruptures 1.1.10 |
| Cron schedule roll-out | croniter-mojo | croniter 6.2.4 |
| Konno-Ohmachi smoothing | obspy-mojo | ObsPy 1.5.1 |
| Electron density grids | cclib-mojo | cclib PyQuante1 path |
| DICOM RLE decode | pydicom-mojo | pydicom 3.0.2 |
| nuScenes detection metrics | nuscenes-eval-mojo | nuscenes-devkit 1.2.0 |
| MOTChallenge metrics | motmetrics-mojo | motmetrics 1.4.0 |

The wheels are real manylinux x86_64 builds of the native Mojo kernels — the Space installs them
from the public [arena-wheels-v0.1.0 release](https://github.com/thyn-ai/mojo-kernels/releases/tag/arena-wheels-v0.1.0)
of [thyn-ai/mojo-kernels](https://github.com/thyn-ai/mojo-kernels) (35 clean-room kernels, Apache-2.0).

## Methodology (the defensibility rulebook)

The harness (`arena/` in this Space's files, plus `benchmarks/` in the repo) mechanically enforces:

- **R1 correctness gate before timing** — kernel output must match the oracle (bit-exact or within
  the documented tolerance printed on the card), else no number is shown. No gate, no numbers.
- **R2 seeded data** — deterministic generators, seed printed on every card; identical bytes to every lane.
- **R4 hardware disclosed** — CPU / cores / RAM / OS / Python / NumPy / harness version in the card footer.
- **R5 cold + warm, both labeled** — cold first call and warm steady state, never blended.
- **R6 median-of-5 with spread** — warm median plus min–max; lanes interleaved A/B/A/B round-robin.
- **R7 incumbent at its best legitimate config** — printed on the card (e.g. bm25s runs its
  numba-compiled scorer; pefile runs `fast_load=True`; ObsPy's batch cell uses its matrix path).
- **R8 end-to-end** — the timed unit returns the materialized answer (scores, checksums, fire
  times, decoded pixels, metrics dicts), never a lazy iterator.
- **R9 published harness** — this Space's source plus the repo's per-kernel `benchmarks/bench_*.py`.
- **R10 honest scope** — we publish the configurations where Algenta wins: each run sweeps the
  duel's configurations and shows the best one the kernel wins, measured live; if none wins on
  this run, the card shows the duel's latest measured win with its real timestamp. Near-parity
  kernels say so in the gallery.

One duel at a time runs (concurrency 1) so timings are never corrupted by a parallel run.

## Tabs

- **⚡ Arena** — pick a duel, press RUN, watch the lanes time live, get a result card with the hero
  speedup, cold/warm bars, parity chip, and a pre-written share post + permalink.
- **🏆 Leaderboard** — latest measured winning result per duel on this Space (resets on Space restart).
- **🧩 Kernel gallery** — all 35 public Mojo kernels with their READMEs' honest speedups.
- **🛡️ Governed agents** — the team's other demo: governed tool calls with execution receipts
  (`pip install algenta-sdk`, self-host free under the Community license; MCP entry
  `io.github.thyn-ai/algenta`).

## Links

- Kernels: [github.com/thyn-ai/mojo-kernels](https://github.com/thyn-ai/mojo-kernels)
- Wheels: [arena-wheels-v0.1.0](https://github.com/thyn-ai/mojo-kernels/releases/tag/arena-wheels-v0.1.0)
- SDK: [github.com/thyn-ai/algenta-sdk](https://github.com/thyn-ai/algenta-sdk) ·
  [integrations](https://github.com/thyn-ai/algenta-integrations)
- Governed agents demo: [thyn-ai/algenta-governed-tool-calls](https://huggingface.co/spaces/thyn-ai/algenta-governed-tool-calls)
