# Algenta × Mojo quickstart

Call the **signed Algenta native runtime** from a **[Mojo](https://docs.modular.com/mojo/)**
program — no Python glue, no HTTP server, just the Mojo standard library and
direct C FFI.

The Algenta engine (closed source) compiles its numeric kernels with Mojo and
ships them inside the signed
[`algenta-runtime-native`](https://pypi.org/project/algenta-runtime-native/)
wheel on PyPI — the same artifact `pip install algenta` resolves
automatically. This example drives that artifact directly from Mojo.

## What it demonstrates

1. **Artifact resolution** — locates the runtime worker executable inside the
   Python environment that [pixi](https://pixi.sh) installs the wheel into
   (override with `$ALGENTA_RUNTIME_LIB`).
2. **Process management** — spawns the worker with `std.os.process.Process`,
   configuring the embedded-interpreter environment it expects
   (`PYTHONHOME` / `MOJO_PYTHON_LIBRARY`).
3. **Mojo FFI** — speaks the runtime's public wire protocol (JSON frames with
   a 4-byte big-endian length prefix over a Unix domain socket) through raw
   `external_call` bindings to libc: `socket`, `connect`, `poll`, `send`,
   `recv`. Mojo's stdlib has no socket module yet, so `main.mojo` doubles as
   a compact reference for POSIX FFI in Mojo.
4. **A deterministic compute round-trip** — the worker evaluates
   `activations.gelu(1.0)` (one of the runtime's published library functions)
   and the demo verifies the result before exiting `0`. Any failure prints an
   `error:` diagnostic and exits `1`.

## Prerequisites

- [pixi](https://pixi.sh) (`curl -fsSL https://pixi.sh/install.sh | sh`)
- A platform with a published runtime wheel:
  - macOS on Apple Silicon (macOS 14+), or
  - Linux x86_64 with glibc ≥ 2.35 (e.g. Ubuntu 22.04+)

There is no Windows or Intel-macOS runtime wheel; those platforms are
intentionally unsupported here.

## Run it

```bash
cd examples/mojo-quickstart
pixi run demo
```

The first run resolves the Mojo toolchain (from Modular's stable `max`
channel), CPython 3.14, and the signed runtime wheel, then compiles
`main.mojo`. Expected output:

```text
Algenta × Mojo quickstart
  python prefix:  …/examples/mojo-quickstart/.pixi/envs/default
  runtime worker: …/site-packages/algenta_runtime_native/algenta-runtime-worker
  launching worker …
  connected: /tmp/algenta-mojo-demo-11782.sock
  < handshake: {"status":"ready"}
  > ping: {"type":"ping"}
  < {"status":"ok"}
  > library_execute activations.gelu: {"type":"library_execute","module":"activations","function":"gelu","args":[1.0]}
  < {"result":0.841191990607477}
  ✓ activations.gelu(1.0) = 0.841191990607477 (deterministic)
  > shutdown: {"type":"shutdown"}
  < {"status":"bye"}
ok: handshake, ping, library_execute and shutdown all succeeded
```

Useful tasks:

| Command          | What it does                                   |
| ---------------- | ---------------------------------------------- |
| `pixi run demo`  | build `main.mojo`, then run the demo (above)   |
| `pixi run build` | compile only, to `./algenta-mojo-demo`         |
| `pixi run dev`   | compile + run in one step (`mojo run`)         |

## How the signed-runtime story works

`algenta-runtime-native` is a wheels-only, per-platform PyPI package carrying
the prebuilt runtime: the `algenta-runtime-worker` executables (the engine's
compiled Mojo kernels, sharded), a `manifest.json` with SHA-256 hashes of
every artifact, and a detached `manifest.sig` signature. The wheel itself is
proprietary data (see its PyPI license field); it contains no importable
public API.

When you use the full Python client (`pip install algenta`), the SDK verifies
the manifest signature and every artifact hash against its embedded trust
anchor before it will execute the runtime — fail-closed. This quickstart
instead relies on the integrity guarantees of the install path itself
(pip/uv verify wheel hashes against PyPI, and `pixi.lock` pins exact
versions) and focuses on the Mojo-side mechanics: process lifecycle, FFI, and
the wire protocol. Treat it as a language integration example, not a
hardened client.

### The wire protocol (public, stable)

```text
launch:    algenta-runtime-worker --server <unix-socket-path>
handshake: worker sends {"status": "ready", ...}     (fields are additive)
ping:      > {"type": "ping"}                        < {"status": "ok"}
execute:   > {"type": "library_execute", "module": M, "function": F, "args": [...]}
           < {"result": ...}
shutdown:  > {"type": "shutdown"}                    < {"status": "bye"}
```

Every frame is a 4-byte big-endian length followed by a UTF-8 JSON payload,
in both directions.

### Environment variables

| Variable             | Meaning                                                            |
| -------------------- | ------------------------------------------------------------------ |
| `ALGENTA_RUNTIME_LIB` | Absolute path to an `algenta-runtime-worker` executable. Overrides site-packages resolution. |
| `CONDA_PREFIX`        | Set automatically by `pixi run`; used as the worker's `PYTHONHOME`. Outside pixi, the demo falls back to a `python3.14` found on `PATH`. |

The worker embeds CPython 3.14 but ships no standard library, so
`PYTHONHOME` must point at a real interpreter installation — the pixi
environment provides one automatically.

## Files

```text
examples/mojo-quickstart/
├── pixi.toml          # workspace: max (Mojo) + CPython 3.14 + the runtime wheel
├── pixi.lock          # pinned, reproducible resolution (commit it)
├── main.mojo          # the demo — read it top to bottom
└── recipe/recipe.yaml # rattler-build recipe for the modular-community channel
```

## Learn more

- [Algenta SDK docs](https://docs.algenta.ai) and the
  [Python SDK](../../packages/python-sdk) / [TypeScript SDK](../../packages/ts-sdk) in this repo
- [`algenta-sdk`](https://pypi.org/project/algenta-sdk/) and
  [`algenta-runtime-native`](https://pypi.org/project/algenta-runtime-native/) on PyPI
- [Mojo manual](https://docs.modular.com/mojo/manual) ·
  [pixi docs](https://pixi.prefix.dev) ·
  [MAX + Mojo conda packages](https://docs.modular.com/max/packages)
