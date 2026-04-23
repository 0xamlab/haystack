---
sidebar_position: 3
---

# CLI

The CLI is now runtime-first as well.

## Install

```bash
pip install algenta-core
```

## Primary command

```bash
algenta demo
```

That runs the branded local deterministic runtime demo and prints:

- connected source metadata
- resolved plan metadata
- query result
- latency and plan hash

## Brandable import preview

```bash
algenta import orders.csv --name orders
```

That runs a branded local import preview and prints:

- source name and origin
- row and field counts
- schema revision
- registration latency
- copy-pasteable next-step code for `Runtime.resolve() -> Runtime.query()`

Important:

- this validates local registration and schema discovery
- it does **not** persist a runtime session across separate CLI invocations

For related exports, the same command supports a local bundle:

```bash
algenta import orders.csv financial.csv ratings.csv
```

That prints a branded bundle summary with imported sources, explicit per-file failures, and deterministic shared-field overlap hints.

## Other supported commands

```bash
algenta map file1.csv [file2.csv ...]
algenta query "total revenue by product line" orders.csv
algenta simulate
algenta benchmark
algenta version
algenta upgrade
```

## Why this matters

The CLI still supports simulation and helper flows, but the first command we recommend is now the runtime demo because it matches the primary product path.
