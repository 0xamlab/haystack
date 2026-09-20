// SPDX-License-Identifier: Apache-2.0
// Unit tests for runtime helper module D: CSV/JSON/SQLite local source readers,
// source naming, import previews, plan hashing and the local execution engine.
import { createHash } from "node:crypto";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import type { ImportFailureResult, LocalRecord } from "./_runtime_constants.js";
import { RuntimeValidationError } from "./_runtime_errors.js";
import { stableHash } from "./_runtime_helpers_a.js";
import {
  aggregateValues,
  coerceRecords,
  exactPlanHash,
  executePlan,
  intentSignature,
  localSourceName,
  looksLikeResolvedPlan,
  parseCsvRows,
  parseCsvText,
  parseJsonText,
  readLocalSource,
  readSqliteSource,
  renderSourceBundlePreview,
  renderSourceImportPreview,
} from "./_runtime_helpers_d.js";
import { hasNodeSqlite } from "./_runtime_test_helpers.js";
import type { ResolvedPlan, SourceRegistrationResponse } from "./types.js";

// Synchronous probe so the sqlite-backed suite can be skipped at describe level: this package
// compiles its tests as CommonJS, where top-level await is unavailable.
const HAS_NODE_SQLITE = ((): boolean => {
  try {
    return Boolean(process.getBuiltinModule("node:sqlite"));
  } catch {
    return false;
  }
})();

type SourceInput = string | LocalRecord[] | Record<string, unknown>;

const SQLITE_ROWS = [
  { product_line: "Alpha", revenue: 120, region: "North" },
  { product_line: "Beta", revenue: 80, region: "South" },
];

let workDir: string;

beforeEach(() => {
  workDir = mkdtempSync(join(tmpdir(), "algenta-ts-helpers-"));
});

afterEach(() => {
  rmSync(workDir, { recursive: true, force: true });
});

function writeFixture(name: string, content: string): string {
  const path = join(workDir, name);
  writeFileSync(path, content);
  return path;
}

function registration(fields: Record<string, unknown>): SourceRegistrationResponse {
  return fields as SourceRegistrationResponse;
}

function assertValidationError(caught: unknown, code: string, messageFragment: string): RuntimeValidationError {
  expect(caught).toBeInstanceOf(RuntimeValidationError);
  const error = caught as RuntimeValidationError;
  expect(error.code).toBe(code);
  expect(error.message).toContain(messageFragment);
  return error;
}

function expectValidationError(run: () => unknown, code: string, messageFragment: string): RuntimeValidationError {
  let caught: unknown;
  try {
    run();
  } catch (error) {
    caught = error;
  }
  return assertValidationError(caught, code, messageFragment);
}

async function expectValidationRejection(
  promise: Promise<unknown>,
  code: string,
  messageFragment: string,
): Promise<RuntimeValidationError> {
  let caught: unknown;
  try {
    await promise;
  } catch (error) {
    caught = error;
  }
  return assertValidationError(caught, code, messageFragment);
}

describe("parseCsvRows", () => {
  it.each<[string, string, string[][]]>([
    ["quoted commas", "a,b\n\"c,d\",e\n", [["a", "b"], ["c,d", "e"]]],
    ["escaped quotes", "\"He said \"\"hi\"\"\",x", [["He said \"hi\"", "x"]]],
    ["CRLF line endings", "a,b\r\n1,2\r\n", [["a", "b"], ["1", "2"]]],
    ["lone CR line endings", "a\rb", [["a"], ["b"]]],
    ["a BOM prefix", "\ufeffa,b\n1,2", [["a", "b"], ["1", "2"]]],
    ["a trailing row without a newline", "a,b\n1,2", [["a", "b"], ["1", "2"]]],
    ["blank lines", "a,b\n\n1,2\n\n", [["a", "b"], ["1", "2"]]],
    ["single-column values", "a\n1\n\n2", [["a"], ["1"], ["2"]]],
    ["a row of empty cells across several columns", "a,b\n,\n", [["a", "b"], ["", ""]]],
    ["an unterminated quoted cell", "a,\"b", [["a", "b"]]],
    ["empty input", "", []],
  ])("parses %s", (_label, text, expected) => {
    expect(parseCsvRows(text)).toEqual(expected);
  });
});

describe("parseCsvText", () => {
  it.each<[string, string]>([
    ["empty text", ""],
    ["whitespace", "  \n "],
    ["a lone empty quoted cell", "\"\""],
    ["a header without rows", "a,b\n"],
  ])("returns no records for %s", (_label, text) => {
    expect(parseCsvText(text)).toEqual([]);
  });

  it("coerces cells per header and skips a header-alias row", () => {
    expect(
      parseCsvText("Order ID,Store Name,Sales Total\norder id,store name,sales total\n1001,Store A,\"1,250\"\n"),
    ).toEqual([{ "Order ID": "1001", "Store Name": "Store A", "Sales Total": 1250 }]);
  });

  it("fills missing trailing cells and suffixes duplicate headers", () => {
    expect(parseCsvText("a,a\n1\n")).toEqual([{ a: 1, a__2: "" }]);
  });
});

describe("parseJsonText", () => {
  it("keeps only object entries of an array", () => {
    expect(parseJsonText("[{\"a\":1}, null, 2, \"x\", {\"b\":2}]")).toEqual([{ a: 1 }, { b: 2 }]);
  });

  it("wraps a single object", () => {
    expect(parseJsonText("{\"a\":1}")).toEqual([{ a: 1 }]);
  });

  it.each([["42"], ["null"], ["\"str\""], ["true"]])("rejects the scalar document %s", text => {
    expectValidationError(
      () => parseJsonText(text),
      "unsupported_json_source",
      "JSON local sources must contain an object or array of objects.",
    );
  });
});

describe("readSqliteSource descriptor validation", () => {
  it.each<[string, Record<string, unknown>, string]>([
    ["no path", { table: "t" }, "Local SQLite descriptors require a path or sqlite connection_string."],
    ["neither table nor query", { path: "x.db" }, "must include exactly one of table or query"],
    ["both table and query", { path: "x.db", table: "t", query: "select 1" }, "must include exactly one of table or query"],
    ["a blank table and a blank query", { path: "x.db", table: " ", query: "  " }, "exactly one of table or query"],
    ["a mutating query", { path: "x.db", query: "DELETE FROM t" }, "read-only SELECT or WITH statement"],
  ])("rejects %s", async (_label, source, message) => {
    await expectValidationRejection(readSqliteSource(source), "invalid_local_source", message);
  });

  it("agrees with the shared hasNodeSqlite helper about sqlite availability", async () => {
    expect(await hasNodeSqlite()).toBe(HAS_NODE_SQLITE);
  });
});

describe.skipIf(!HAS_NODE_SQLITE)("readSqliteSource and coerceRecords with node:sqlite", () => {
  let dbPath: string;

  beforeEach(async () => {
    dbPath = join(workDir, "orders.db");
    const { DatabaseSync } = await import("node:sqlite");
    const database = new DatabaseSync(dbPath);
    try {
      database.exec("CREATE TABLE orders (product_line TEXT, revenue REAL, region TEXT)");
      const insert = database.prepare("INSERT INTO orders (product_line, revenue, region) VALUES (?, ?, ?)");
      for (const row of SQLITE_ROWS) {
        insert.run(row.product_line, row.revenue, row.region);
      }
    } finally {
      database.close();
    }
  });

  it("reads a whole table", async () => {
    await expect(readSqliteSource({ path: dbPath, table: "orders" })).resolves.toEqual(SQLITE_ROWS);
  });

  it("runs SELECT and WITH queries", async () => {
    await expect(
      readSqliteSource({ path: dbPath, query: " select product_line from orders where revenue > 100 " }),
    ).resolves.toEqual([{ product_line: "Alpha" }]);
    await expect(
      readSqliteSource({
        path: dbPath,
        query: "WITH big AS (SELECT * FROM orders WHERE revenue > 100) SELECT region FROM big",
      }),
    ).resolves.toEqual([{ region: "North" }]);
  });

  it("accepts a sqlite connection string in place of a path", async () => {
    await expect(readSqliteSource({ connection_string: `sqlite:///${dbPath}`, table: "orders" })).resolves.toEqual(
      SQLITE_ROWS,
    );
  });

  it("wraps read failures with the descriptor path", async () => {
    const missing = await expectValidationRejection(
      readSqliteSource({ path: dbPath, table: "missing" }),
      "invalid_local_source",
      "Unable to read the requested local SQLite source.",
    );
    expect(missing.details.path).toBe(dbPath);
    expect(String(missing.details.error)).toContain("no such table");

    const garbagePath = writeFixture("garbage.db", "this is not a database file at all");
    const garbage = await expectValidationRejection(
      readSqliteSource({ path: garbagePath, table: "orders" }),
      "invalid_local_source",
      "Unable to read the requested local SQLite source.",
    );
    expect(String(garbage.details.error)).toContain("not a database");
  });

  it("routes sqlite descriptors through coerceRecords", async () => {
    await expect(coerceRecords({ type: "sqlite", path: dbPath, table: "orders" })).resolves.toEqual(SQLITE_ROWS);
    await expect(
      coerceRecords({ provider: "sqlite3", path: dbPath, query: "select region from orders where revenue < 100" }),
    ).resolves.toEqual([{ region: "South" }]);
    await expect(coerceRecords({ connection_string: `sqlite:///${dbPath}`, table: "orders" })).resolves.toEqual(
      SQLITE_ROWS,
    );
  });
});

describe("readLocalSource", () => {
  it("reads CSV and JSON files by suffix, case-insensitively", () => {
    expect(readLocalSource(writeFixture("orders.CSV", "a,b\n1,x\n"))).toEqual([{ a: 1, b: "x" }]);
    expect(readLocalSource(writeFixture("orders.json", "[{\"a\":1}]"))).toEqual([{ a: 1 }]);
  });

  it("rejects a missing file", () => {
    const path = join(workDir, "missing.csv");
    const error = expectValidationError(
      () => readLocalSource(path),
      "local_source_not_found",
      "could not read the requested source path",
    );
    expect(error.details.source).toBe(path);
    expect(String(error.details.error)).toContain("ENOENT");
  });

  it("rejects unsupported suffixes", () => {
    const path = writeFixture("orders.txt", "a,b");
    const error = expectValidationError(
      () => readLocalSource(path),
      "unsupported_local_source",
      "currently supports only CSV and JSON file paths",
    );
    expect(error.details).toEqual({ source: path, suffix: ".txt" });
  });
});

describe("localSourceName", () => {
  it.each<[string, SourceInput, string]>([
    ["a posix path", "/data/exports/orders.csv", "orders"],
    ["a windows path", "C:\\data\\orders.v2.json", "orders.v2"],
    ["an empty string", "", "source_3"],
    ["in-memory records", [{ a: 1 }], "source_3"],
    ["an envelope location", { type: "csv", location: { path: "/data/orders.csv" } }, "orders"],
    ["an explicit name", { name: " Custom ", path: "/data/orders.csv" }, "Custom"],
    ["a path with a table", { path: "/data/app.db", table: " orders " }, "app_orders"],
    ["a path with a query", { path: "/data/app.db", query: "select 1" }, "app_query"],
    ["a bare path", { path: "/data/app.db" }, "app"],
    ["a sqlite connection string", { connection_string: "sqlite:///tmp/app.db", table: "t" }, "app_t"],
    ["a path that is only an extension", { path: "/data/.csv" }, "source_3"],
    ["inline records", { records: [{ a: 1 }] }, "source_3"],
    ["an empty descriptor", {}, "source_3"],
  ])("names %s", (_label, source, expected) => {
    expect(localSourceName(source, 3)).toBe(expected);
  });
});

describe("renderSourceImportPreview", () => {
  it("falls back to placeholders for missing metadata", () => {
    const out = renderSourceImportPreview(registration({ source_schema: { fields: [] } }), { color: false });
    expect(out).toContain("| Mode: local | Status: ready ");
    expect(out).toContain("| Source: source ");
    expect(out).toContain("| Origin: source ");
    expect(out).toContain("| Rows: unknown | Fields: 0 ");
    expect(out).toContain("| Preview: (no schema fields detected) ");
    expect(out).toContain("| Schema: n/a | Latency: n/a ");
    expect(out).not.toContain("\u001b[");
  });

  it("lists up to three fields and counts the rest", () => {
    const out = renderSourceImportPreview(
      registration({
        status: "ready",
        name: "orders",
        row_count: 3,
        latency_ms: 12.3456,
        planner_schema_revision: "abcdefghijklmnop",
        source_schema: { fields: ["a", "b", "c", "d", "e"] },
      }),
      { mode: "api", sourceRef: "orders.csv", color: false },
    );
    expect(out).toContain("| Mode: api | Status: ready ");
    expect(out).toContain("| Source: orders ");
    expect(out).toContain("| Origin: orders.csv ");
    expect(out).toContain("| Rows: 3 | Fields: 5 ");
    expect(out).toContain("| Preview: a, b, c, +2 more ");
    expect(out).toContain("| Schema: abcdefghijkl | Latency: 12.346ms ");
  });

  it("joins three or fewer fields verbatim and falls back to dataset_name", () => {
    const out = renderSourceImportPreview(
      registration({ status: "pending", dataset_name: "ds", schema: { columns: [{ name: "a" }, { name: "b" }, { name: "c" }] } }),
      { color: true },
    );
    expect(out).toContain("Status: pending");
    expect(out).toContain("Source: ds");
    expect(out).toContain("Preview: a, b, c ");
    expect(out).toContain("\u001b[");
  });

  it("defers the color decision to the banner when no options are given", () => {
    const out = renderSourceImportPreview(registration({ status: "ready", name: "orders", source_schema: { fields: ["a"] } }));
    expect(out).toContain("Mode: local | Status: ready");
    expect(out).toContain("Preview: a ");
  });
});

describe("renderSourceBundlePreview", () => {
  it("renders placeholders for an empty bundle", () => {
    const out = renderSourceBundlePreview([], [], { color: false });
    expect(out).toContain("| Mode: local | Imported: 0 | Failures: 0 ");
    expect(out).toContain("| Rows: 0 ");
    expect(out).toContain("| - (no sources imported) ");
    expect(out).toContain("| - No deterministic shared-field overlaps detected. ");
    expect(out).toContain("| - None ");
    expect(out).not.toContain("\u001b[");
  });

  it("lists sources, shared fields and at most three failures", () => {
    const orders = registration({ status: "ready", name: "orders", row_count: 10, source_schema: { fields: ["customer_id", "total"] } });
    const customers = registration({ status: "ready", dataset_name: "customers", row_count: null, schema: { columns: [{ name: "customer_id" }] } });
    const anonymous = registration({ status: "ready" });
    const failures: ImportFailureResult[] = [
      { sourceRef: "a.csv", code: "local_source_not_found", message: "m", name: "alpha" },
      { sourceRef: "b.csv", code: "unsupported_local_source", message: "m" },
      { sourceRef: "c.csv", code: "invalid_local_source", message: "m" },
      { sourceRef: "d.csv", code: "hidden_by_cap", message: "m" },
    ];
    const out = renderSourceBundlePreview([orders, customers, anonymous], failures, { mode: "api", color: true });
    expect(out).toContain("Mode: api | Imported: 3 | Failures: 4");
    expect(out).toContain("Rows: 10 ");
    expect(out).toContain("- orders ");
    expect(out).toContain("- customers ");
    expect(out).toContain("- source ");
    expect(out).toContain("- orders.customer_id <-> customers.customer_id");
    expect(out).toContain("- alpha: local_source_not_found");
    expect(out).toContain("- b.csv: unsupported_local_source");
    expect(out).toContain("- c.csv: invalid_local_source");
    expect(out).not.toContain("hidden_by_cap");
    expect(out).toContain("\u001b[");
  });

  it("defers the color decision to the banner when no options are given", () => {
    expect(renderSourceBundlePreview([], [])).toContain("Mode: local | Imported: 0 | Failures: 0");
  });
});

describe("exactPlanHash and looksLikeResolvedPlan", () => {
  const plan: ResolvedPlan = {
    source_name: "orders",
    metric_column: "revenue",
    aggregation: "sum",
    group_column: null,
    schema_revision: "rev",
  };

  it("hashes the null-stripped plan independent of key order", () => {
    const reordered: ResolvedPlan = { schema_revision: "rev", aggregation: "sum", metric_column: "revenue", source_name: "orders" };
    expect(exactPlanHash(plan)).toBe(exactPlanHash(reordered));
    expect(exactPlanHash(plan)).toBe(
      createHash("sha256")
        .update("{\"aggregation\":\"sum\",\"metric_column\":\"revenue\",\"schema_revision\":\"rev\",\"source_name\":\"orders\"}")
        .digest("hex"),
    );
    expect(exactPlanHash({ ...plan, limit: 5 })).not.toBe(exactPlanHash(plan));
  });

  it.each<[unknown, boolean]>([
    [null, false],
    [5, false],
    ["plan", false],
    [{ source_name: "s", metric_column: "m" }, false],
    [{ source_name: "s", schema_revision: "r" }, false],
    [{ metric_column: "m", schema_revision: "r" }, false],
    [{ source_name: "s", metric_column: "m", schema_revision: "r" }, true],
  ])("looksLikeResolvedPlan(%j) is %j", (value, expected) => {
    expect(looksLikeResolvedPlan(value)).toBe(expected);
  });
});

describe("intentSignature", () => {
  it("hashes the normalized request with defaults", () => {
    expect(intentSignature("orders", {}, "rev")).toBe(
      stableHash({
        source_name: "orders",
        schema_revision: "rev",
        metric: "",
        group_by: "",
        aggregation: "sum",
        limit: null,
        order: "desc",
        constraints: {},
        filter: {},
      }),
    );
  });

  it("normalizes metric, group_by, aggregation and order", () => {
    const request = {
      metric: " Net Sales ",
      group_by: "Region",
      aggregation: "Total",
      limit: 5,
      order: "ASC",
      constraints: { a: 1 },
      filter: { conditions: [] },
    };
    expect(intentSignature("orders", request, "rev")).toBe(
      stableHash({
        source_name: "orders",
        schema_revision: "rev",
        metric: "net sales",
        group_by: "region",
        aggregation: "sum",
        limit: 5,
        order: "asc",
        constraints: { a: 1 },
        filter: { conditions: [] },
      }),
    );
    expect(intentSignature("orders", { raw_text: "average revenue" }, "rev")).not.toBe(intentSignature("orders", {}, "rev"));
  });
});

describe("coerceRecords", () => {
  it("reads a file path", async () => {
    await expect(coerceRecords(writeFixture("orders.csv", "a,b\n1,x\n"))).resolves.toEqual([{ a: 1, b: "x" }]);
  });

  it("copies in-memory records", async () => {
    const input = [{ a: 1 }];
    const output = await coerceRecords(input);
    expect(output).toEqual(input);
    expect(output[0]).not.toBe(input[0]);
  });

  it("filters non-object entries from a records descriptor", async () => {
    await expect(coerceRecords({ type: "csv", records: [{ a: 1 }, null, "x", 2] })).resolves.toEqual([{ a: 1 }]);
  });

  it("follows a descriptor path", async () => {
    await expect(coerceRecords({ type: "csv", path: writeFixture("orders.csv", "a\n1\n") })).resolves.toEqual([{ a: 1 }]);
    await expect(coerceRecords({ path: writeFixture("orders.json", "{\"a\":2}") })).resolves.toEqual([{ a: 2 }]);
  });

  it("wraps a plain object as a single record", async () => {
    await expect(coerceRecords({ a: 1, b: "two" })).resolves.toEqual([{ a: 1, b: "two" }]);
  });

  it("propagates connector and sqlite descriptor errors", async () => {
    await expectValidationRejection(coerceRecords({ type: "csv" }), "unsupported_local_connector", "local path or inline data");
    await expectValidationRejection(coerceRecords({ type: "sqlite", table: "t" }), "invalid_local_source", "require a path");
  });
});

describe("aggregateValues", () => {
  it.each<[string, number[], number | null]>([
    ["count", [], 0],
    ["count", [1, 2], 2],
    ["sum", [], 0],
    ["sum", [1, 2.5], 3.5],
    ["avg", [], null],
    ["avg", [1, 2, 3], 2],
    ["min", [], null],
    ["min", [3, 1], 1],
    ["max", [], null],
    ["max", [3, 9], 9],
    ["Total", [1], 1],
    ["mean", [2, 4], 3],
  ])("%s over %j is %j", (aggregation, values, expected) => {
    expect(aggregateValues(values, aggregation)).toBe(expected);
  });

  it("rejects unknown aggregations", () => {
    expectValidationError(() => aggregateValues([1], "median"), "invalid_aggregation", "median");
  });
});

describe("executePlan", () => {
  const RECORDS: LocalRecord[] = [
    { region: "North", revenue: 10 },
    { region: "South", revenue: 5 },
    { region: "North", revenue: "7" },
    { region: "South", revenue: "n/a" },
    { region: null, revenue: 1 },
  ];

  it.each<[string | null | undefined]>([[undefined], [null], [""]])(
    "aggregates a single row with the admitted count when the group column is %j",
    groupColumn => {
      expect(executePlan(RECORDS, "revenue", groupColumn, "sum", 10)).toEqual([{ revenue: 23, count: 4 }]);
    },
  );

  it("groups, sorts by the metric descending and applies the limit", () => {
    expect(executePlan(RECORDS, "revenue", "region", "sum", 10)).toEqual([
      { region: "North", revenue: 17, count: 2 },
      { region: "South", revenue: 5, count: 1 },
      { region: null, revenue: 1, count: 1 },
    ]);
    expect(executePlan(RECORDS, "revenue", "region", "sum", 2)).toEqual([
      { region: "North", revenue: 17, count: 2 },
      { region: "South", revenue: 5, count: 1 },
    ]);
  });

  it("sorts groups without a numeric metric last", () => {
    const records: LocalRecord[] = [
      { region: "A", revenue: "x" },
      { region: "B", revenue: 2 },
      { region: "C", revenue: 9 },
    ];
    expect(executePlan(records, "revenue", "region", "avg", 10)).toEqual([
      { region: "C", revenue: 9, count: 1 },
      { region: "B", revenue: 2, count: 1 },
      { region: "A", revenue: null, count: 0 },
    ]);
  });

  it("groups object labels by their canonical rendering", () => {
    const records: LocalRecord[] = [
      { tag: { b: 1, a: 2 }, v: 1 },
      { tag: { a: 2, b: 1 }, v: 2 },
      { tag: { a: 3 }, v: 5 },
    ];
    expect(executePlan(records, "v", "tag", "sum", 10)).toEqual([
      { tag: { a: 3 }, v: 5, count: 1 },
      { tag: { b: 1, a: 2 }, v: 3, count: 2 },
    ]);
  });
});
