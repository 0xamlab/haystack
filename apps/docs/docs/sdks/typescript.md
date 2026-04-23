---
sidebar_position: 2
---

# TypeScript SDK

The primary TypeScript path is now the same runtime-first contract as Python:

- `Runtime.connect(...)`
- `Runtime.resolve(...)`
- optional `Runtime.verify(...)`
- `Runtime.query(...)`

Use the low-level `DecisionEngineClient` only when you want raw API control.

## Installation

```bash
npm install decision-engine-sdk
```

## Runtime-first quickstart

```typescript
import { Runtime } from "decision-engine-sdk";

const rt = new Runtime();

await rt.connect("orders.csv", { name: "orders" });

const plan = await rt.resolve({
  source_name: "orders",
  metric: "revenue",
  group_by: "product_line",
});

const verified = await rt.verify(plan);
if (!verified.valid) {
  throw new Error(verified.errors.join("; "));
}

const result = await rt.query(plan);
console.log(result.result);
```

## Brandable import preview

For a brandable onboarding/import step before `resolve -> query`, use:

```typescript
import { Runtime } from "decision-engine-sdk";

const rt = new Runtime();

const imported = await rt.importPreview(
  "orders.csv",
  {
    name: "orders",
    sourceRef: "orders.csv",
  },
);

console.log(imported.preview);
```

That returns:

- the registration metadata
- a reusable branded preview string for terminal or Node-based onboarding surfaces

The formatter is pure. It does not print implicitly and it does not create hidden session state.

For a related multi-source onboarding step, use:

```typescript
import { Runtime } from "decision-engine-sdk";

const rt = new Runtime();

const imported = await rt.importBundlePreview(
  [
    "orders.csv",
    "financial.csv",
    {
      provider: "sqlite",
      path: "/data/orders.db",
      table: "orders",
    },
  ],
  {
    sourceRefs: ["orders.csv", "financial.csv", "orders.db#orders"],
  },
);

console.log(imported.preview);
```

That returns:

- the successful registrations
- explicit per-source failures when one source is empty or invalid
- a reusable branded bundle preview string with deterministic shared-field hints

## What this proves

- the same `resolve -> verify -> query` path works in TypeScript
- local deterministic execution can run without credentials
- TypeScript no longer has to drop straight to the raw API client for the primary path
- TypeScript can now expose a brandable import/onboarding surface without leaving the runtime contract

## Local mode

`Runtime()` defaults to local mode.

Use it when:

- you want deterministic local execution
- you are prototyping with local CSV/JSON files, in-memory records, or local SQLite descriptors
- you want the published primary path without hosted control-plane setup

Current local TypeScript scope is intentionally narrow and deterministic:

- local CSV and JSON file paths
- local SQLite descriptors when the Node runtime exposes `node:sqlite`
- in-memory records
- structured `resolve`
- optional `verify`
- deterministic `query`

SQLite example:

```typescript
import { Runtime } from "decision-engine-sdk";

const rt = new Runtime();

await rt.connect(
  {
    provider: "sqlite",
    path: "/data/orders.db",
    table: "orders",
  },
  { name: "orders" },
);
```

If you explicitly opt into hosted local mode with a live API key, TypeScript can keep execution local while enforcing the stored local device license and local credit bucket offline:

```typescript
import { Runtime } from "decision-engine-sdk";

const rt = new Runtime({
  apiKey: process.env.ALGENTA_API_KEY,
});

await rt.connect("orders.csv", { name: "orders" });
const plan = await rt.resolve({
  source_name: "orders",
  metric: "revenue",
  group_by: "product_line",
});
const result = await rt.query(plan);
console.log(result.result);
```

That hosted-local behavior is opt-in. Plain `new Runtime()` remains outside the hosted device-license and credit-bucket path.

## API mode

Use API mode when you want hosted source registration and the broader direct API surface.

```typescript
import { Runtime } from "decision-engine-sdk";

const rt = new Runtime({
  mode: "api",
  apiKey: process.env.ALGENTA_API_KEY,
});

const plan = await rt.resolve({
  source_name: "orders",
  metric: "revenue",
  group_by: "product_line",
});

const result = await rt.query(plan);
console.log(result.result);
```

API mode is also the runtime-first path for broader connector descriptors such as hosted databases:

```typescript
import { Runtime } from "decision-engine-sdk";

const rt = new Runtime({
  mode: "api",
  apiKey: process.env.ALGENTA_API_KEY,
});

await rt.connect(
  {
    type: "postgres",
    location: {
      host: "db.example.com",
      port: 5432,
      database: "orders",
      schema: "public",
      table: "orders",
    },
    auth: {
      credentials: {
        user: "analytics",
        password: "secret",
      },
    },
  },
  { name: "orders_pg" },
);
```

That same `Runtime.connect(...)` API-mode contract is also where you pass:

- MySQL or warehouse-style structured database descriptors
- S3/object-storage source descriptors
- REST resource descriptors exposed by the hosted connector layer

## Advanced: direct API client

If you need low-level control, use `DecisionEngineClient` directly:

```typescript
import { DecisionEngineClient } from "decision-engine-sdk";

const client = new DecisionEngineClient({
  apiKey: process.env.ALGENTA_API_KEY,
});

const plan = await client.resolve({
  source_name: "orders",
  metric: "revenue",
  group_by: "product_line",
});

const result = await client.query(plan.resolved_plan ?? plan);
console.log(result.result);
```

Use the direct client when:

- you want the raw REST/API surface
- you are integrating with existing API-oriented infrastructure
- you need advanced endpoints beyond the runtime-first happy path

## Current truth vs target model

Today, TypeScript supports both:

- a runtime-first facade for the primary path
- the lower-level direct API client

Target direction remains:

- local-first runtime
- `resolve -> query` as the default user model
- direct API client as an advanced surface
