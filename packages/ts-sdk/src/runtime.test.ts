import { createHash, createHmac } from "node:crypto";
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve as resolvePath } from "node:path";

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  Runtime,
  RuntimeConfigurationError,
  RuntimeValidationError,
  renderSourceBundlePreview,
  renderSourceImportPreview,
} from "./runtime.js";

const REAL_MARCH_ORDERS = resolvePath(
  process.cwd(),
  "..",
  "..",
  "test_files",
  "850a28da-a6f7-4ecc-9e7a-51a9cf7f501b-united_states.csv",
);
const REAL_MARCH_FINANCIAL = resolvePath(
  process.cwd(),
  "..",
  "..",
  "test_files",
  "aaeff3ab-19ac-494e-9e58-e507bd7e3893-united_states.csv",
);
const REAL_MARCH_EMPTY = resolvePath(
  process.cwd(),
  "..",
  "..",
  "test_files",
  "549c63c8-3300-416c-8b45-55fec4c6529a_store_pause_2026-03-01_2026-03-31.csv",
);

const ORIGINAL_ENV = { ...process.env };

function runtimeTempDir(): string {
  return mkdtempSync(join(tmpdir(), "algenta-ts-runtime-"));
}

function base64UrlJson(value: Record<string, unknown>): string {
  return Buffer.from(JSON.stringify(value)).toString("base64url");
}

function issueControlPlaneLicense(apiKey: string): string {
  const header = base64UrlJson({ alg: "HS256", typ: "JWT" });
  const payload = base64UrlJson({
    api_key_prefix: apiKey.slice(0, 12),
    device_id: "ts-device-1",
    plan: "pro",
    device_limit: 5,
    permitted_modules: ["*"],
    issued_at: Math.floor(Date.now() / 1000),
    expires_at: 0,
    grace_days: 14,
    iss: "algenta-control-plane",
    sub: "device-license",
  });
  const jwtSeed = process.env.ALGENTA_JWT_SECRET ?? "change-me-in-production-use-256-bit-random-value";
  const secret = createHash("sha256")
    .update(`${jwtSeed}:license-signing`)
    .digest("hex");
  const signature = createHmac("sha256", secret).update(`${header}.${payload}`).digest("base64url");
  return `${header}.${payload}.${signature}`;
}

function seedStoredLicense(runtimeDir: string, apiKey: string): void {
  writeFileSync(join(runtimeDir, "license.jwt"), issueControlPlaneLicense(apiKey), { mode: 0o600 });
}

function seedCredits(runtimeDir: string, remaining: number, total = remaining): void {
  const now = Date.now() / 1000;
  writeFileSync(
    join(runtimeDir, "credits.json"),
    `${JSON.stringify(
      {
        credits_remaining: remaining,
        credits_total: total,
        issued_at: now,
        expires_at: now + 3600,
        billing_period: "2026-04",
        refresh_after: now + 1800,
      },
      null,
      2,
    )}\n`,
  );
}

async function hasNodeSqlite(): Promise<boolean> {
  try {
    await import("node:sqlite");
    return true;
  } catch {
    return false;
  }
}

async function writeSqliteFixture(
  path: string,
  rows: Array<Record<string, string | number>>,
  table = "orders",
): Promise<void> {
  const { DatabaseSync } = await import("node:sqlite");
  const database = new DatabaseSync(path);
  try {
    database.exec(`DROP TABLE IF EXISTS "${table}"`);
    database.exec(
      `CREATE TABLE "${table}" ("product_line" TEXT, "revenue" REAL, "region" TEXT)`,
    );
    const statement = database.prepare(
      `INSERT INTO "${table}" ("product_line", "revenue", "region") VALUES (?, ?, ?)`,
    );
    for (const row of rows) {
      statement.run(row.product_line, row.revenue, row.region);
    }
  } finally {
    database.close();
  }
}

beforeEach(() => {
  delete process.env.ALGENTA_RUNTIME_DIR;
  delete process.env.ALGENTA_JWT_SECRET;
  delete process.env.ALGENTA_CONTROL_PLANE_URL;
  delete process.env.ALGENTA_API_KEY;
  delete process.env.DE_API_KEY;
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

afterEach(() => {
  const runtimeDir = process.env.ALGENTA_RUNTIME_DIR;
  for (const key of Object.keys(process.env)) {
    if (!(key in ORIGINAL_ENV)) {
      delete process.env[key];
    }
  }
  Object.assign(process.env, ORIGINAL_ENV);
  if (runtimeDir && runtimeDir.includes("algenta-ts-runtime-")) {
    rmSync(runtimeDir, { force: true, recursive: true });
  }
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("Runtime", () => {
  it("supports local resolve and query happy path", async () => {
    const runtime = new Runtime();
    await runtime.connect(
      [
        { product_line: "Electronics", revenue: 42_193_221 },
        { product_line: "Apparel", revenue: 28_114_992 },
      ],
      { name: "orders" },
    );

    const plan = await runtime.resolve({
      source_name: "orders",
      metric: "revenue",
      group_by: "product_line",
    });

    expect(plan.resolved_plan?.metric_column).toBe("revenue");
    expect(plan.resolved_plan?.group_column).toBe("product_line");

    const result = await runtime.query(plan);
    expect(result.result_type).toBe("table");
    expect(result.row_count).toBe(2);
    expect(result.plan_hash).toBeTruthy();
  });

  it("verifies local plans", async () => {
    const runtime = new Runtime();
    await runtime.connect([{ product_line: "Electronics", revenue: 10 }], { name: "orders" });
    const plan = await runtime.resolve({
      source_name: "orders",
      metric: "revenue",
      group_by: "product_line",
    });

    const verified = await runtime.verify(plan);
    expect(verified.valid).toBe(true);
    expect(verified.verification_mode).toBe("local");
  });

  it("rejects schema revision mismatch in local query", async () => {
    const runtime = new Runtime();
    await runtime.connect([{ product_line: "Electronics", revenue: 10 }], { name: "orders" });
    const plan = await runtime.resolve({
      source_name: "orders",
      metric: "revenue",
      group_by: "product_line",
    });

    await expect(
      runtime.query({
        ...(plan.resolved_plan ?? {}),
        schema_revision: "stale-schema",
      }),
    ).rejects.toBeInstanceOf(RuntimeValidationError);
  });

  it("requires API configuration when api mode has no key or client", async () => {
    const runtime = new Runtime({ mode: "api" });
    await expect(runtime.resolve({ source_name: "orders", metric: "revenue" })).rejects.toBeInstanceOf(
      RuntimeConfigurationError,
    );
  });

  it("delegates resolve, verify, query, and connect to the injected api client", async () => {
    let capturedResolve: Record<string, unknown> | null = null;
    let capturedVerify: Record<string, unknown> | null = null;
    let capturedQuery: Record<string, unknown> | null = null;
    const fakeClient = {
      registerSource: async () => ({ status: "ready", source_id: "src_1" }),
      resolve: async (request: Record<string, unknown>) => {
        capturedResolve = request;
        return {
        resolved_plan: {
          source_name: "orders",
          metric_column: "revenue",
          aggregation: "sum",
          schema_revision: "schema-1",
        },
        confidence: 1,
        plan: ["Use orders"],
        explanation: ["Resolved exactly"],
        resolved_column: "revenue",
        resolved_role: "measure",
        resolved_source: "orders",
        candidates: [],
        source_scores: { orders: 1 },
        latency_ms: 1,
        decision_path: "exact_spec",
        plan_hash: "plan-1",
        schema_revision: "schema-1",
        validated: true,
        deterministic_scope: "api",
        confidence_source: "schema_truth",
        clarification_required: false,
        rejection_reason: null,
        request_id: "req_1",
        intent_signature: "intent-1",
        source_set: ["orders"],
        join_path: [],
        planner_mode: "exact_spec",
      };
      },
      verify: async (request: Record<string, unknown>) => {
        capturedVerify = request;
        return {
        valid: true,
        errors: [],
        suggestions: [],
        resolved: { source_name: "orders" },
        latency_ms: 1,
      };
      },
      query: async (request: Record<string, unknown>) => {
        capturedQuery = request;
        return {
        query_id: "query-1",
        result: 42,
        result_type: "scalar",
        confidence: 1,
        plan: ["Use orders"],
        resolved_column: "revenue",
        resolved_role: "measure",
        resolved_source: "orders",
        row_count: 1,
        candidates: [],
        source_scores: { orders: 1 },
        ambiguous: false,
        exact_spec: true,
        explanation: ["Executed exactly"],
        latency_ms: 1,
        decision_path: "exact_spec",
        plan_hash: "plan-1",
        schema_revision: "schema-1",
        validated: true,
        deterministic_scope: "api",
        confidence_source: "schema_truth",
        clarification_required: false,
        rejection_reason: null,
        request_id: "req_2",
        source_set: ["orders"],
        join_path: [],
        planner_mode: "exact_spec",
      };
      },
    };

    const runtime = new Runtime({
      mode: "api",
      client: fakeClient as never,
    });

    const registered = await runtime.connect({ records: [{ revenue: 42, product_line: "Electronics" }] });
    const plan = await runtime.resolve({ source_name: "orders", metric: "revenue" });
    const verified = await runtime.verify(plan);
    const result = await runtime.query(plan);

    expect(registered.source_id).toBe("src_1");
    expect(plan.resolved_plan?.metric_column).toBe("revenue");
    expect(verified.valid).toBe(true);
    expect(result.result).toBe(42);
    expect(capturedResolve).toEqual({
      preferred_source: "orders",
      allow_org_scope: true,
      metric: {
        role: "metric",
        hint: "revenue",
      },
    });
    expect(capturedVerify).toMatchObject({
      resolved_plan: {
        source_name: "orders",
        metric_column: "revenue",
        schema_revision: "schema-1",
      },
    });
    expect(capturedQuery).toMatchObject({
      resolved_plan: {
        source_name: "orders",
        metric_column: "revenue",
        schema_revision: "schema-1",
      },
    });
  });

  it("uses an exact api resolve for registered source fields when schema metadata is known", async () => {
    let resolveCalls = 0;
    const fakeClient = {
      registerSource: async () => ({
        status: "ready",
        source_id: "src_1",
        dataset_id: "src_1",
        name: "orders",
        source_schema: { fields: ["product_line", "revenue", "region"] },
        planner_schema_revision: "planner_schema_1",
      }),
      request: async () => ({
        entry: {
          source_schema_revision: "registry_schema_1",
        },
      }),
      resolve: async () => {
        resolveCalls += 1;
        throw new Error("exact api resolve should not call client.resolve");
      },
      verify: async () => ({
        valid: true,
        errors: [],
        suggestions: [],
        resolved: { source_name: "orders" },
        latency_ms: 1,
      }),
      query: async (request: Record<string, unknown>) => ({
        query_id: "query-1",
        result: 2,
        result_type: "scalar",
        confidence: 1,
        plan: ["Execute exact plan."],
        resolved_column: String(
          (request.resolved_plan as Record<string, unknown> | undefined)?.metric_column,
        ),
        resolved_role: "measure",
        resolved_source: String(
          (request.resolved_plan as Record<string, unknown> | undefined)?.source_name,
        ),
        row_count: 1,
        candidates: [],
        source_scores: { orders: 1 },
        ambiguous: false,
        exact_spec: true,
        explanation: ["Executed exactly."],
        latency_ms: 1,
        decision_path: "exact_spec",
        plan_hash: "plan-1",
        schema_revision: "registry_schema_1",
        validated: true,
        deterministic_scope: "api",
        confidence_source: "schema_truth",
        clarification_required: false,
        rejection_reason: null,
        request_id: "req_2",
        source_set: ["orders"],
        join_path: [],
        planner_mode: "exact_spec",
      }),
    };

    const runtime = new Runtime({
      mode: "api",
      client: fakeClient as never,
    });

    await runtime.connect({ records: [{ revenue: 42, product_line: "Electronics" }] }, { name: "orders" });
    const plan = await runtime.resolve({
      source_name: "orders",
      metric: "revenue",
      group_by: "product_line",
      aggregation: "count",
    });
    const verified = await runtime.verify(plan);
    const result = await runtime.query(plan);

    expect(resolveCalls).toBe(0);
    expect(plan.resolved_plan?.source_name).toBe("orders");
    expect(plan.resolved_plan?.metric_column).toBe("revenue");
    expect(plan.resolved_plan?.group_column).toBe("product_line");
    expect(plan.schema_revision).toBe("registry_schema_1");
    expect(verified.valid).toBe(true);
    expect(result.result).toBe(2);
  });

  it("delegates structured database descriptors to the injected api client", async () => {
    const cases: Array<{ source: Record<string, unknown>; expectedName: string }> = [
      {
        source: {
          type: "postgres",
          connection_string: "postgresql://analytics:secret@localhost:5432/orders",
          schema: "public",
          table: "orders",
        },
        expectedName: "orders_pg",
      },
      {
        source: {
          type: "mysql",
          connection_string: "mysql://analytics:secret@localhost:3306/orders",
          database: "orders",
          table: "orders",
        },
        expectedName: "orders_mysql",
      },
      {
        source: {
          type: "s3",
          bucket: "algenta-public",
          key: "orders/orders.csv",
          format: "csv",
        },
        expectedName: "orders_s3",
      },
      {
        source: {
          type: "rest",
          base_url: "https://example.com/api",
          path: "/orders",
          method: "GET",
        },
        expectedName: "orders_rest",
      },
    ];
    const captured: Array<{ source: Record<string, unknown>; options: Record<string, unknown> }> = [];
    const fakeClient = {
      registerSource: async (
        source: Record<string, unknown>,
        options: Record<string, unknown>,
      ) => {
        captured.push({ source, options });
        return {
          status: "ready",
          source_id: "src_pg_1",
          dataset_id: "src_pg_1",
          name: String(source.name ?? "source"),
          source_schema: { fields: ["order_id", "revenue"] },
          planner_schema_revision: "schema_pg_1",
          latency_ms: 3.4,
          row_count: 120,
        };
      },
    };

    const runtime = new Runtime({
      mode: "api",
      client: fakeClient as never,
    });

    for (const { source, expectedName } of cases) {
      const registration = await runtime.connect(
        source,
        { name: expectedName, description: `Primary ${expectedName} source` },
      );

      expect(registration.name).toBe(expectedName);
    }

    expect(captured).toEqual(
      cases.map(({ source, expectedName }) => ({
        source:
          source.type === "postgres"
            ? {
                name: expectedName,
                connection: {
                  type: "sql",
                  provider: "postgres",
                  connection_string: "postgresql://analytics:secret@localhost:5432/orders",
                  schema: "public",
                  table: "orders",
                  query: "SELECT * FROM public.orders",
                },
              }
            : source.type === "mysql"
              ? {
                  name: expectedName,
                  connection: {
                    type: "sql",
                    provider: "mysql",
                    connection_string: "mysql://analytics:secret@localhost:3306/orders",
                    table: "orders",
                    query: "SELECT * FROM orders",
                  },
                }
              : source.type === "s3"
                ? {
                    name: expectedName,
                    connection: {
                      type: "s3",
                      bucket: "algenta-public",
                      key: "orders/orders.csv",
                      file_type: "csv",
                    },
                  }
                : {
                    name: expectedName,
                    connection: {
                      type: "rest_api",
                      url: "https://example.com/api/orders",
                      path: "/orders",
                      method: "GET",
                    },
                  },
        options: {
          description: `Primary ${expectedName} source`,
        },
      })),
    );
  });

  it("accepts canonical connector envelopes in api mode", async () => {
    const cases: Array<{
      source: Record<string, unknown>;
      expectedName: string;
      expectedConnection: Record<string, unknown>;
    }> = [
      {
        source: {
          type: "postgres",
          location: {
            host: "localhost",
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
        expectedName: "orders_pg",
        expectedConnection: {
          type: "sql",
          provider: "postgres",
          connection_string: "postgresql://analytics:secret@localhost:5432/orders",
          schema: "public",
          table: "orders",
          query: "SELECT * FROM public.orders",
        },
      },
      {
        source: {
          type: "s3",
          location: { bucket: "algenta-public", key: "orders/orders.csv" },
          options: { format: "csv" },
        },
        expectedName: "orders_s3",
        expectedConnection: {
          type: "s3",
          bucket: "algenta-public",
          key: "orders/orders.csv",
          file_type: "csv",
        },
      },
      {
        source: {
          type: "rest",
          location: { base_url: "https://example.com/api", path: "/orders" },
          auth: { mode: "token", credentials: { token: "secret-token" } },
          options: { method: "GET" },
        },
        expectedName: "orders_rest",
        expectedConnection: {
          type: "rest_api",
          url: "https://example.com/api/orders",
          path: "/orders",
          method: "GET",
          headers: { Authorization: "Bearer secret-token" },
        },
      },
      {
        source: {
          type: "csv",
          location: { path: REAL_MARCH_ORDERS },
          options: { delimiter: "," },
        },
        expectedName: "orders_csv",
        expectedConnection: {
          type: "file",
          file_type: "csv",
          file_path: REAL_MARCH_ORDERS,
          delimiter: ",",
        },
      },
    ];
    const captured: Array<{ source: Record<string, unknown>; options: Record<string, unknown> }> = [];
    const fakeClient = {
      registerSource: async (
        source: Record<string, unknown>,
        options: Record<string, unknown>,
      ) => {
        captured.push({ source, options });
        return {
          status: "ready",
          source_id: "src_pg_1",
          dataset_id: "src_pg_1",
          name: String(source.name ?? "source"),
          source_schema: { fields: ["order_id", "revenue"] },
          planner_schema_revision: "schema_pg_1",
          latency_ms: 3.4,
          row_count: 120,
        };
      },
    };

    const runtime = new Runtime({
      mode: "api",
      client: fakeClient as never,
    });

    for (const { source, expectedName } of cases) {
      const registration = await runtime.connect(
        source,
        { name: expectedName, description: `Primary ${expectedName} source` },
      );

      expect(registration.name).toBe(expectedName);
    }

    expect(captured).toEqual(
      cases.map(({ expectedName, expectedConnection }) => ({
        source: {
          name: expectedName,
          connection: expectedConnection,
        },
        options: {
          description: `Primary ${expectedName} source`,
        },
      })),
    );
  });

  it("accepts canonical csv connectors in local mode", async () => {
    const runtimeDir = runtimeTempDir();
    try {
      const csvPath = join(runtimeDir, "orders.csv");
      writeFileSync(csvPath, "product_line,revenue\nElectronics,10\nApparel,20\n");

      const runtime = new Runtime();
      const registration = await runtime.connect(
        {
          type: "csv",
          location: { path: csvPath },
          options: { delimiter: "," },
        },
        { name: "orders" },
      );
      const plan = await runtime.resolve({
        source_name: "orders",
        metric: "revenue",
        aggregation: "count",
      });
      const result = await runtime.query(plan);

      expect(registration.row_count).toBe(2);
      expect(plan.resolved_plan?.source_name).toBe("orders");
      expect(result.result).toBe(2);
    } finally {
      rmSync(runtimeDir, { recursive: true, force: true });
    }
  });

  it("rejects remote canonical connectors in local mode", async () => {
    const runtime = new Runtime();

    await expect(
      runtime.connect({
        type: "postgres",
        location: {
          host: "localhost",
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
      }),
    ).rejects.toMatchObject({ code: "unsupported_local_connector" });
  });

  it("returns a branded import preview for local sources", async () => {
    const runtime = new Runtime();
    const imported = await runtime.importPreview(
      [{ product_line: "Electronics", revenue: 42_193_221, region: "US" }],
      { name: "orders", sourceRef: "orders.csv", color: false },
    );

    expect(imported.registration.name).toBe("orders");
    expect(imported.registration.row_count).toBe(1);
    expect(imported.preview).toContain("Algenta Source Import");
    expect(imported.preview).toContain("Source: orders");
    expect(imported.preview).toContain("Origin: orders.csv");
    expect(imported.preview).toContain("Rows: 1 | Fields: 3");
  });

  it("renders a pure import preview from registration metadata", () => {
    const preview = renderSourceImportPreview(
      {
        name: "orders",
        status: "ready",
        row_count: 2,
        planner_schema_revision: "schema_revision_123456",
        latency_ms: 4.2,
        source_schema: { fields: ["product_line", "revenue", "region", "country"] },
      },
      { sourceRef: "orders.csv", mode: "local", color: false },
    );

    expect(preview).toContain("Algenta Source Import");
    expect(preview).toContain("Mode: local | Status: ready");
    expect(preview).toContain("Preview: product_line, revenue, region, +1 more");
    expect(preview).toContain("Schema: schema_revis | Latency: 4.200ms");
  });

  it("renders a pure bundle preview from registration and failure metadata", () => {
    const preview = renderSourceBundlePreview(
      [
        {
          source_id: "src_1",
          dataset_id: "src_1",
          name: "orders_detail",
          status: "ready",
          row_count: 6097,
          planner_schema_revision: "schema_orders_123456",
          latency_ms: 12.5,
          source_schema: { fields: ["Order ID", "Store Name", "Sales (incl. tax)"] },
        },
        {
          source_id: "src_2",
          dataset_id: "src_2",
          name: "orders_financial",
          status: "ready",
          row_count: 2026,
          planner_schema_revision: "schema_financial_123456",
          latency_ms: 8.3,
          source_schema: {
            fields: [
              "Order ID as per Uber Eats manager",
              "Store name as per Uber Eats manager",
            ],
          },
        },
      ],
      [
        {
          sourceRef: "store_pause.csv",
          code: "empty_source",
          message: "Connected source is empty and cannot be queried.",
          name: "store_pause",
        },
      ],
      { color: false },
    );

    expect(preview).toContain("Algenta Source Bundle");
    expect(preview).toContain("Imported: 2 | Failures: 1");
    expect(preview).toContain("orders_detail");
    expect(preview).toContain("orders_financial");
    expect(preview).toContain("store_pause: empty_source");
  });

  it("supports local file-backed CSV import preview and query for real corpus files", async () => {
    const runtime = new Runtime();
    const imported = await runtime.importPreview(REAL_MARCH_ORDERS, {
      name: "orders_detail",
      sourceRef: "orders_detail.csv",
      color: false,
    });

    const plan = await runtime.resolve({
      source_name: "orders_detail",
      metric: "Sales (incl. tax)",
      group_by: "Order Channel",
    });
    const result = await runtime.query(plan);

    expect(imported.registration.row_count).toBe(6097);
    expect(imported.preview).toContain("Origin: orders_detail.csv");
    expect(plan.resolved_plan?.metric_column).toBe("Sales (incl. tax)");
    expect(plan.resolved_plan?.group_column).toBe("Order Channel");
    expect(result.result_type).toBe("table");
    expect(result.row_count).toBeGreaterThan(0);
  });

  it("supports branded bundle previews across real csv and local sqlite sources", async () => {
    if (!(await hasNodeSqlite())) {
      return;
    }
    const runtimeDir = runtimeTempDir();
    const dbPath = join(runtimeDir, "orders.db");
    await writeSqliteFixture(dbPath, [
      { product_line: "Electronics", revenue: 42_193_221, region: "US" },
      { product_line: "Apparel", revenue: 28_114_992, region: "US" },
    ]);

    const runtime = new Runtime();
    const bundle = await runtime.importBundlePreview(
      [
        REAL_MARCH_ORDERS,
        {
          provider: "sqlite",
          path: dbPath,
          table: "orders",
        },
        REAL_MARCH_EMPTY,
      ],
      {
        sourceRefs: ["orders_detail.csv", "orders.db#orders", REAL_MARCH_EMPTY.split(/[\\/]/).pop()],
        color: false,
      },
    );

    expect(bundle.registrations).toHaveLength(2);
    expect(bundle.failures).toHaveLength(1);
    expect(bundle.preview).toContain("Algenta Source Bundle");
    expect(bundle.preview).toContain("Imported: 2 | Failures: 1");
    expect(bundle.preview).toContain("orders_orders");
    expect(bundle.preview).toContain("empty_source");
  });

  it("supports api-mode bundle previews across mixed connector descriptors", async () => {
    const seen: Array<Record<string, unknown>> = [];
    const fakeClient = {
      registerSource: async (
        source: Record<string, unknown>,
        options: Record<string, unknown>,
      ) => {
        seen.push(source);
        const connection = source.connection;
        if (connection && typeof connection === "object" && (connection as Record<string, unknown>).type === "rest_api") {
          throw new RuntimeValidationError(
            "upstream_validation_failed",
            "REST source rejected by hosted connector validation.",
            { source: (connection as Record<string, unknown>).url },
          );
        }
        return {
          source_id: `src_${seen.length}`,
          dataset_id: `src_${seen.length}`,
          name: String(source.name ?? "source"),
          status: "ready",
          row_count: 120,
          planner_schema_revision: `schema_${seen.length}`,
          latency_ms: 3.4,
          source_schema: { fields: ["order_id", "revenue", "store_name"] },
        };
      },
    };

    const runtime = new Runtime({
      mode: "api",
      client: fakeClient as never,
    });

    const bundle = await runtime.importBundlePreview(
      [
        {
          type: "postgres",
          location: {
            host: "localhost",
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
        {
          type: "s3",
          bucket: "algenta-public",
          key: "orders/orders.csv",
          format: "csv",
        },
        {
          type: "rest",
          base_url: "https://example.com/api",
          path: "/orders",
          method: "GET",
        },
      ],
      {
        names: ["orders_pg", "orders_s3", "orders_rest"],
        sourceRefs: [
          "postgres://orders",
          "s3://algenta-public/orders/orders.csv",
          "https://example.com/api/orders",
        ],
        color: false,
      },
    );

    expect(bundle.registrations).toHaveLength(2);
    expect(bundle.failures).toHaveLength(1);
    expect(bundle.failures[0]?.code).toBe("upstream_validation_failed");
    expect(bundle.preview).toContain("Algenta Source Bundle");
    expect(bundle.preview).toContain("Imported: 2 | Failures: 1");
    expect(bundle.preview).toContain("orders_pg");
    expect(bundle.preview).toContain("orders_s3");
    expect(bundle.preview).toContain("orders_rest: upstream_validation_failed");
    expect(seen.map(source => String(source.name))).toEqual(["orders_pg", "orders_s3", "orders_rest"]);
    expect(
      seen.map(source => String((source.connection as Record<string, unknown>).type)),
    ).toEqual(["sql", "s3", "rest_api"]);
  });

  it("supports connectMany across related real csv sources with explicit names", async () => {
    const runtime = new Runtime();
    const registrations = await runtime.connectMany(
      [REAL_MARCH_ORDERS, REAL_MARCH_FINANCIAL],
      { names: ["orders_detail", "orders_financial"] },
    );

    expect(registrations).toHaveLength(2);
    expect(registrations[0]?.name).toBe("orders_detail");
    expect(registrations[0]?.row_count).toBe(6097);
    expect(registrations[1]?.name).toBe("orders_financial");
    expect(registrations[1]?.row_count).toBe(2026);
  });

  it("skips alias header rows in real financial csv files", async () => {
    const runtime = new Runtime();
    const registration = await runtime.connect(REAL_MARCH_FINANCIAL, { name: "orders_financial" });

    expect(registration.row_count).toBe(2026);
  });

  it("supports local sqlite descriptors when node:sqlite is available", async () => {
    if (!(await hasNodeSqlite())) {
      return;
    }
    const runtimeDir = runtimeTempDir();
    const dbPath = join(runtimeDir, "orders.db");
    await writeSqliteFixture(dbPath, [
      { product_line: "Electronics", revenue: 42_193_221, region: "US" },
      { product_line: "Apparel", revenue: 28_114_992, region: "US" },
    ]);

    const runtime = new Runtime();
    const registration = await runtime.connect({
      provider: "sqlite",
      path: dbPath,
      table: "orders",
    });
    const plan = await runtime.resolve({
      source_name: registration.name,
      metric: "revenue",
      group_by: "product_line",
    });
    const result = await runtime.query(plan);

    expect(registration.name).toBe("orders_orders");
    expect(registration.row_count).toBe(2);
    expect(result.row_count).toBe(2);
  });

  it("renders sqlite descriptor origins cleanly in import previews", async () => {
    if (!(await hasNodeSqlite())) {
      return;
    }
    const runtimeDir = runtimeTempDir();
    const dbPath = join(runtimeDir, "orders.db");
    await writeSqliteFixture(dbPath, [
      { product_line: "Electronics", revenue: 42_193_221, region: "US" },
      { product_line: "Apparel", revenue: 28_114_992, region: "US" },
    ]);

    const runtime = new Runtime();
    const imported = await runtime.importPreview({
      provider: "sqlite",
      path: dbPath,
      table: "orders",
    });

    expect(imported.registration.name).toBe("orders_orders");
    expect(imported.preview).toContain(`Origin: orders.db#orders`);
  });

  it("rejects empty real csv exports", async () => {
    const runtime = new Runtime();

    await expect(runtime.connect(REAL_MARCH_EMPTY, { name: "store_pause" })).rejects.toBeInstanceOf(
      RuntimeValidationError,
    );
  });

  it("enforces hosted local limits offline with a stored license on real csv files", async () => {
    const runtimeDir = runtimeTempDir();
    process.env.ALGENTA_RUNTIME_DIR = runtimeDir;
    process.env.ALGENTA_JWT_SECRET = "ts-runtime-test-secret";
    seedStoredLicense(runtimeDir, "de_live_ts_runtime_key");
    seedCredits(runtimeDir, 2, 2);
    vi.stubGlobal("fetch", vi.fn(async () => {
      throw new Error("offline");
    }));

    const runtime = new Runtime({ apiKey: "de_live_ts_runtime_key" });
    await runtime.connect(REAL_MARCH_ORDERS, { name: "orders_detail" });
    const plan = await runtime.resolve({
      source_name: "orders_detail",
      metric: "Sales (incl. tax)",
      group_by: "Order Channel",
    });

    const first = await runtime.query(plan);
    const second = await runtime.query(plan);

    expect(first.row_count).toBeGreaterThan(0);
    expect(second.row_count).toBeGreaterThan(0);
    await expect(runtime.query(plan)).rejects.toMatchObject({ code: "quota_exhausted" });
    expect(JSON.parse(readFileSync(join(runtimeDir, "credits.json"), "utf8")).credits_remaining).toBe(0);
  });

  it("blocks first-time offline hosted local execution without a stored license", async () => {
    const runtimeDir = runtimeTempDir();
    process.env.ALGENTA_RUNTIME_DIR = runtimeDir;
    process.env.ALGENTA_JWT_SECRET = "ts-runtime-test-secret";
    vi.stubGlobal("fetch", vi.fn(async () => {
      throw new Error("offline");
    }));

    const runtime = new Runtime({ apiKey: "de_live_ts_runtime_key" });
    await runtime.connect(REAL_MARCH_ORDERS, { name: "orders_detail" });
    const plan = await runtime.resolve({
      source_name: "orders_detail",
      metric: "Sales (incl. tax)",
      group_by: "Order Channel",
    });

    await expect(runtime.query(plan)).rejects.toMatchObject({
      code: "license_required",
      message: expect.stringContaining("reachable control plane"),
    });
  });

  it("keeps plain local runtime outside hosted local enforcement", async () => {
    const runtimeDir = runtimeTempDir();
    process.env.ALGENTA_RUNTIME_DIR = runtimeDir;
    const fetchSpy = vi.fn(async () => {
      throw new Error("hosted path should not run");
    });
    vi.stubGlobal("fetch", fetchSpy);

    const runtime = new Runtime();
    await runtime.connect(REAL_MARCH_ORDERS, { name: "orders_detail" });
    const plan = await runtime.resolve({
      source_name: "orders_detail",
      metric: "Sales (incl. tax)",
      group_by: "Order Channel",
    });
    const result = await runtime.query(plan);

    expect(result.row_count).toBeGreaterThan(0);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("seeds stored license and local credits from control-plane registration", async () => {
    const runtimeDir = runtimeTempDir();
    process.env.ALGENTA_RUNTIME_DIR = runtimeDir;
    process.env.ALGENTA_JWT_SECRET = "ts-runtime-test-secret";
    const fetchSpy = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/v1/device/register")) {
        return new Response(
          JSON.stringify({
            license_token: issueControlPlaneLicense("de_live_ts_runtime_key"),
            credits_granted: 2,
            credits_billing_period: "2026-04",
            credits_expires_at: Math.floor(Date.now() / 1000) + 3600,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      return new Response(JSON.stringify({ credits_granted: 0 }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });
    vi.stubGlobal("fetch", fetchSpy);

    const runtime = new Runtime({ apiKey: "de_live_ts_runtime_key" });
    await runtime.connect(REAL_MARCH_ORDERS, { name: "orders_detail" });
    const plan = await runtime.resolve({
      source_name: "orders_detail",
      metric: "Sales (incl. tax)",
      group_by: "Order Channel",
    });
    const result = await runtime.query(plan);

    expect(result.row_count).toBeGreaterThan(0);
    expect(existsSync(join(runtimeDir, "license.jwt"))).toBe(true);
    expect(JSON.parse(readFileSync(join(runtimeDir, "credits.json"), "utf8")).credits_remaining).toBe(1);
    expect(fetchSpy).toHaveBeenCalled();
  });
});
