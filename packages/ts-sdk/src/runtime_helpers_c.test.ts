// SPDX-License-Identifier: Apache-2.0
// Unit tests for runtime helper module C: bundle overlap summaries, source
// references, canonical connector envelopes, API connection normalization and
// CSV header/scalar coercion.
import { resolve as resolvePath } from "node:path";
import { describe, expect, it } from "vitest";

import type { LocalRecord } from "./_runtime_constants.js";
import { RuntimeValidationError } from "./_runtime_errors.js";
import {
  baseHeaderName,
  bundleOverlapLines,
  canonicalizeCsvHeaders,
  coerceCsvScalar,
  csvFieldTokens,
  csvIsIdentifierField,
  fileConnectorType,
  flattenConnectorEnvelope,
  isCanonicalConnectorEnvelope,
  looksLikeHeaderAliasRow,
  mergeConnectorSection,
  normalizeApiSourcePayload,
  normalizeConnectorAuth,
  normalizeLocalRuntimeSource,
  normalizeRuntimeConnection,
  runtimeApiSourceName,
  runtimeRestUrl,
  runtimeSqlConnectionString,
  runtimeSqlQuery,
  sourceDescriptorPath,
  sourceReference,
  sqlIdentifier,
  stripUndefined,
} from "./_runtime_helpers_c.js";
import type { SourceRegistrationResponse } from "./types.js";

type SourceInput = string | LocalRecord[] | Record<string, unknown>;

function registration(fields: Record<string, unknown>): SourceRegistrationResponse {
  return fields as SourceRegistrationResponse;
}

function expectValidationError(run: () => unknown, code: string, messageFragment: string): RuntimeValidationError {
  let caught: unknown;
  try {
    run();
  } catch (error) {
    caught = error;
  }
  expect(caught).toBeInstanceOf(RuntimeValidationError);
  const error = caught as RuntimeValidationError;
  expect(error.code).toBe(code);
  expect(error.message).toContain(messageFragment);
  return error;
}

/** normalizeConnectorAuth mutates in place; return the mutated copy for table assertions. */
function normalizedAuth(input: Record<string, unknown>): Record<string, unknown> {
  const copy = { ...input };
  normalizeConnectorAuth(copy);
  return copy;
}

describe("bundleOverlapLines", () => {
  it("lists shared fields between registrations, strongest overlap first", () => {
    const orders = registration({ name: "orders", source_schema: { fields: ["zeta_id", "alpha_beta_gamma", "total"] } });
    const customers = registration({
      name: null,
      dataset_name: "customers",
      schema: { columns: [{ name: "zeta_id" }, { name: "alpha_beta_delta" }] },
    });
    // The 0.667 alpha/beta overlap sorts alphabetically before zeta_id, so score must win.
    expect(bundleOverlapLines([orders, customers])).toEqual([
      "orders.zeta_id <-> customers.zeta_id",
      "orders.alpha_beta_gamma <-> customers.alpha_beta_delta",
    ]);
  });

  it("caps the summary at three lines and names anonymous sources by position", () => {
    const anonymous = (): SourceRegistrationResponse => registration({ source_schema: { fields: ["id", "key"] } });
    expect(bundleOverlapLines([anonymous(), anonymous(), anonymous()])).toEqual([
      "source_1.id <-> source_2.id",
      "source_1.id <-> source_3.id",
      "source_1.key <-> source_2.key",
    ]);
  });

  it("returns nothing without overlaps", () => {
    const left = registration({ name: "a", source_schema: { fields: ["x"] } });
    const right = registration({ name: "b", source_schema: { fields: ["y"] } });
    expect(bundleOverlapLines([left, right])).toEqual([]);
    expect(bundleOverlapLines([])).toEqual([]);
  });
});

describe("sourceReference", () => {
  it.each<[string, SourceInput, string | undefined, string]>([
    ["an explicit reference", {}, "  explicit ", "explicit"],
    ["a posix file path", "/data/exports/orders.csv", undefined, "orders.csv"],
    ["a windows file path with a blank explicit reference", "C:\\data\\orders.csv", "  ", "orders.csv"],
    ["in-memory records", [{ a: 1 }], undefined, "in-memory records"],
    ["a sqlite envelope with a table", { type: "sqlite", location: { path: "/data/db.sqlite", table: " orders " } }, undefined, "db.sqlite#orders"],
    ["a descriptor with a query", { path: "/data/db.sqlite", query: "select 1" }, undefined, "db.sqlite#query"],
    ["a bare path descriptor", { path: "/data/db.sqlite", table: "  " }, undefined, "db.sqlite"],
    ["a sqlite connection string", { connection_string: "sqlite:///tmp/app.db" }, undefined, "app.db"],
    ["a named descriptor", { name: " nm " }, undefined, "nm"],
    ["an anonymous descriptor", { records: [] }, undefined, "structured source descriptor"],
  ])("describes %s", (_label, source, explicitRef, expected) => {
    expect(sourceReference(source, explicitRef)).toBe(expected);
  });
});

describe("sourceDescriptorPath", () => {
  it.each<[Record<string, unknown>, string | null]>([
    [{ path: " /x " }, "/x"],
    [{ connection_string: "sqlite:////abs/app.db" }, "/abs/app.db"],
    [{ connection_string: " SQLite+pysqlite:///rel/app.db " }, "rel/app.db"],
    [{ connection_string: "postgresql://h/db" }, null],
    [{ path: "  ", connection_string: "  " }, null],
    [{}, null],
  ])("resolves %j", (source, expected) => {
    expect(sourceDescriptorPath(source)).toBe(expected);
  });
});

describe("stripUndefined and isCanonicalConnectorEnvelope", () => {
  it("drops undefined and null entries", () => {
    expect(stripUndefined({ a: undefined, b: null, c: 0, d: "" })).toEqual({ c: 0, d: "" });
  });

  it.each<[Record<string, unknown>, boolean]>([
    [{ location: {} }, true],
    [{ auth: {} }, true],
    [{ options: {} }, true],
    [{ type: "csv", path: "x" }, false],
  ])("classifies %j", (source, expected) => {
    expect(isCanonicalConnectorEnvelope(source)).toBe(expected);
  });
});

describe("mergeConnectorSection", () => {
  it("skips absent sections", () => {
    const target = { a: 1 };
    mergeConnectorSection(target, undefined, "location");
    mergeConnectorSection(target, null, "options");
    expect(target).toEqual({ a: 1 });
  });

  it.each<[string, unknown]>([
    ["an array", ["x"]],
    ["a string", "x"],
    ["a number", 5],
    ["false", false],
  ])("rejects %s", (_label, section) => {
    const error = expectValidationError(
      () => mergeConnectorSection({}, section, "location"),
      "invalid_connector",
      "Canonical connector location must be an object.",
    );
    expect(error.details).toEqual({ section: "location" });
  });

  it("merges new keys and tolerates identical duplicates", () => {
    const target: Record<string, unknown> = { path: "/x" };
    mergeConnectorSection(target, { path: "/x", table: "t" }, "location");
    expect(target).toEqual({ path: "/x", table: "t" });
  });

  it("rejects conflicting values", () => {
    const error = expectValidationError(
      () => mergeConnectorSection({ path: "/x" }, { path: "/y" }, "location"),
      "connector_conflict",
      "Canonical connector defines conflicting values for 'path'.",
    );
    expect(error.details).toEqual({ field: "path", section: "location" });
  });
});

describe("normalizeConnectorAuth", () => {
  it.each<[string, Record<string, unknown>, Record<string, unknown>]>([
    ["no auth mode", { token: "t" }, { token: "t" }],
    ["mode none", { auth_mode: "none", token: "t" }, { token: "t" }],
    ["token", { auth_mode: "Token", token: " t0k " }, { headers: { Authorization: "Bearer t0k" } }],
    ["bearer via access_token", { auth_mode: "bearer", access_token: "abc" }, { headers: { Authorization: "Bearer abc" } }],
    ["oauth via api_key (api_key retained)", { auth_mode: "oauth", api_key: "k" }, { api_key: "k", headers: { Authorization: "Bearer k" } }],
    [
      "token with an existing Authorization header",
      { auth_mode: "token", token: "x", headers: { Authorization: "Custom y" } },
      { headers: { Authorization: "Custom y" } },
    ],
    ["basic", { auth_mode: "basic", username: "u", password: "p" }, { headers: { Authorization: "Basic dTpw" } }],
    [
      "basic via user with an existing Authorization header",
      { auth_mode: "basic", user: "u", password: "p", headers: { Authorization: "Custom" } },
      { user: "u", headers: { Authorization: "Custom" } },
    ],
    [
      "api_key with a custom header name",
      { auth_mode: "api_key", api_key: "k", api_key_header: " X-Custom " },
      { api_key: "k", api_key_header: " X-Custom ", headers: { "X-Custom": "k" } },
    ],
    ["api_key via the header alias", { auth_mode: "api_key", api_key: "k", header: "X-Alias" }, { api_key: "k", headers: { "X-Alias": "k" } }],
    ["api_key via token with the default header", { auth_mode: "api_key", token: " k " }, { headers: { "X-API-Key": "k" } }],
    [
      "api_key with an existing header value",
      { auth_mode: "api_key", api_key: "k", headers: { "X-API-Key": "keep" } },
      { api_key: "k", headers: { "X-API-Key": "keep" } },
    ],
  ])("normalizes %s", (_label, input, expected) => {
    expect(normalizedAuth(input)).toEqual(expected);
  });

  it.each<[string, Record<string, unknown>, string, Record<string, unknown>]>([
    ["token without credentials", { auth_mode: "token" }, "Bearer-style connector auth requires token, access_token, or api_key.", { mode: "token" }],
    ["bearer with a blank credential", { auth_mode: "bearer", token: "  " }, "Bearer-style connector auth requires", { mode: "bearer" }],
    ["basic without a password", { auth_mode: "basic", username: "u" }, "Basic connector auth requires username/user and password.", { mode: "basic" }],
    ["api_key without credentials", { auth_mode: "api_key", api_key_header: "X" }, "API key connector auth requires api_key or token credentials.", { mode: "api_key" }],
    ["headers given as a string", { auth_mode: "token", token: "t", headers: "nope" }, "Canonical connector headers must be an object.", { field: "headers" }],
    ["headers given as an array", { auth_mode: "token", token: "t", headers: ["nope"] }, "Canonical connector headers must be an object.", { field: "headers" }],
    ["an unsupported mode", { auth_mode: "digest", token: "t" }, "Unsupported connector auth mode 'digest'.", { mode: "digest" }],
  ])("rejects %s", (_label, input, message, details) => {
    const error = expectValidationError(() => normalizedAuth(input), "invalid_connector_auth", message);
    expect(error.details).toEqual(details);
  });
});

describe("flattenConnectorEnvelope", () => {
  it.each<[Record<string, unknown>]>([[{ location: {} }], [{ type: "  " }], [{ type: 5 }]])(
    "requires a non-empty type for %j",
    source => {
      const error = expectValidationError(
        () => flattenConnectorEnvelope(source),
        "invalid_connector",
        "Canonical connectors require a non-empty type.",
      );
      expect(error.details).toEqual({ field: "type" });
    },
  );

  it("flattens location, auth and options into one API descriptor", () => {
    expect(
      flattenConnectorEnvelope({
        type: " REST-API ",
        description: undefined,
        location: { url: "https://api.example.com/items" },
        auth: { mode: " Token ", credentials: { token: "abc" } },
        options: { timeout: 5, headers: { "X-Trace": "1" } },
      }),
    ).toEqual({
      type: "rest_api",
      url: "https://api.example.com/items",
      headers: { "X-Trace": "1", Authorization: "Bearer abc" },
      timeout: 5,
    });
  });

  it.each<[string, unknown]>([
    ["a string", "x"],
    ["an array", []],
    ["null", null],
  ])("rejects auth given as %s", (_label, auth) => {
    const error = expectValidationError(
      () => flattenConnectorEnvelope({ type: "rest", auth }),
      "invalid_connector",
      "Canonical connector auth must be an object.",
    );
    expect(error.details).toEqual({ field: "auth" });
  });

  it("keeps auth_mode verbatim for non-API connectors", () => {
    expect(flattenConnectorEnvelope({ type: "csv", location: { path: "/x.csv" }, auth: { mode: "token" } })).toEqual({
      type: "csv",
      path: "/x.csv",
      auth_mode: "token",
    });
  });

  it("hoists auth.headers entries to top-level keys like every other section", () => {
    // Shared contract with the Python SDK and the connector service: each section contributes
    // top-level keys, so `auth.headers` is not itself the HTTP headers map.
    expect(flattenConnectorEnvelope({ type: "rest", location: { url: "u" }, auth: { headers: { "X-Trace": "1" } } })).toEqual({
      type: "rest",
      url: "u",
      "X-Trace": "1",
    });
  });

  it("rejects conflicting top-level and section values", () => {
    expectValidationError(
      () => flattenConnectorEnvelope({ type: "csv", path: "/a", location: { path: "/b" } }),
      "connector_conflict",
      "conflicting values for 'path'",
    );
  });
});

describe("fileConnectorType", () => {
  it.each<[Record<string, unknown>, string]>([
    [{ type: "XLSX" }, "excel"],
    [{ type: "xls" }, "excel"],
    [{ type: " CSV " }, "csv"],
    [{ provider: "json" }, "json"],
    [{}, ""],
  ])("maps %j", (source, expected) => {
    expect(fileConnectorType(source)).toBe(expected);
  });
});

describe("normalizeLocalRuntimeSource", () => {
  it.each<[string, Record<string, unknown>, Record<string, unknown>]>([
    ["a file path", { type: "csv", path: " /data/orders.csv " }, { path: "/data/orders.csv" }],
    ["a file_path alias", { type: "json", file_path: "/data/orders.json" }, { path: "/data/orders.json" }],
    ["an envelope location", { type: "CSV", location: { path: "/data/orders.csv" } }, { path: "/data/orders.csv" }],
    ["inline records", { type: "parquet", records: [{ a: 1 }] }, { records: [{ a: 1 }] }],
    ["inline csv", { type: "csv", csv: "a,b\n1,2" }, { csv: "a,b\n1,2" }],
    ["inline tsv", { type: "tsv", csv: "a\tb" }, { csv: "a\tb" }],
    ["inline json", { type: "json", json_str: "[]" }, { json_str: "[]" }],
    [
      "a sqlite descriptor (undefined entries dropped)",
      { type: "sqlite", path: "/db.sqlite", table: "t", extra: undefined },
      { type: "sqlite", path: "/db.sqlite", table: "t" },
    ],
    [
      "a sqlite3 provider",
      { provider: "sqlite3", path: "/db.sqlite", query: "select 1" },
      { provider: "sqlite3", path: "/db.sqlite", query: "select 1" },
    ],
    ["an untyped descriptor", { records: [{ a: 1 }] }, { records: [{ a: 1 }] }],
  ])("normalizes %s", (_label, source, expected) => {
    expect(normalizeLocalRuntimeSource(source)).toEqual(expected);
  });

  it.each<[Record<string, unknown>]>([
    [{ type: "csv" }],
    [{ type: "csv", json_str: "[]" }],
    [{ type: "json", csv: "a" }],
    [{ type: "excel", path: "  " }],
  ])("rejects file connector %j without a local path or inline data", source => {
    const error = expectValidationError(
      () => normalizeLocalRuntimeSource(source),
      "unsupported_local_connector",
      "canonical file connectors only with a local path or inline data",
    );
    expect(error.details).toEqual({ type: source.type });
  });

  it.each<[Record<string, unknown>, string]>([
    [{ provider: "postgres", host: "h" }, "postgres"],
    [{ connection_type: "BigQuery" }, "bigquery"],
    [{ type: "rest", location: { url: "u" } }, "rest"],
  ])("rejects remote connector %j with the API-mode hint", (source, type) => {
    const error = expectValidationError(
      () => normalizeLocalRuntimeSource(source),
      "unsupported_local_connector",
      "Use Runtime({ mode: 'api', apiKey: '...' })",
    );
    expect(error.details).toEqual({ type });
  });
});

describe("runtimeApiSourceName", () => {
  it.each<[Record<string, unknown>, string | undefined, string]>([
    [{ name: "ignored" }, " Explicit ", "Explicit"],
    [{ name: " nm " }, "  ", "nm"],
    [{ path: "/data/orders.csv" }, undefined, "orders"],
    [{}, undefined, "source_0"],
  ])("names %j", (source, explicitName, expected) => {
    expect(runtimeApiSourceName(source, explicitName)).toBe(expected);
  });
});

describe("sqlIdentifier", () => {
  it.each<[string, string]>([
    ["orders", "orders"],
    [" orders ", "orders"],
    ["a$b_1", "a$b_1"],
    ["_x", "_x"],
  ])("accepts %j", (value, expected) => {
    expect(sqlIdentifier(value, "table")).toBe(expected);
  });

  it.each<[unknown]>([[""], ["  "], [5], [null], [undefined]])("requires a non-empty string for %j", value => {
    const error = expectValidationError(
      () => sqlIdentifier(value, "table"),
      "invalid_sql_descriptor",
      "API and self_hosted SQL descriptors require a non-empty table.",
    );
    expect(error.details).toEqual({ field: "table" });
  });

  it.each([["bad-name"], ["1abc"], ["a.b"], ["a b"]])("rejects the complex identifier %j", value => {
    const error = expectValidationError(
      () => sqlIdentifier(value, "schema"),
      "invalid_sql_identifier",
      "only auto-build queries for simple schema/table identifiers",
    );
    expect(error.details).toEqual({ field: "schema", value });
  });
});

describe("runtimeSqlConnectionString", () => {
  it("returns an explicit connection_string trimmed", () => {
    expect(runtimeSqlConnectionString("postgres", { connection_string: " postgresql://x ", host: "ignored" })).toBe(
      "postgresql://x",
    );
  });

  it.each<[string, Record<string, unknown>, string]>([
    ["postgres", { host: "db.local", database: "app" }, "postgresql://db.local:5432/app"],
    ["postgresql", { host: " db.local ", database: "app", user: "u", password: "p@ss" }, "postgresql://u:p%40ss@db.local:5432/app"],
    ["mysql", { host: "db.local", database: "app", username: "u" }, "mysql://u@db.local:3306/app"],
    ["mssql", { host: "db.local", database: "app", port: 1444 }, "mssql://db.local:1444/app"],
    ["redshift", { host: "db.local", database: "app", port: "5440" }, "redshift://db.local:5440/app"],
    ["postgres", { host: "db.local", database: "my db", user: "u", password: "" }, "postgresql://u:@db.local:5432/my%20db"],
  ])("builds a %s DSN from %j", (provider, source, expected) => {
    expect(runtimeSqlConnectionString(provider, source)).toBe(expected);
  });

  it.each<[string, Record<string, unknown>, string, string]>([
    ["a non-string password", { host: "h", database: "d", user: "u", password: 123 }, "Database connector password must be a string when provided.", "password"],
    ["a non-string user", { host: "h", database: "d", user: 5 }, "Database connector user must be a string when provided.", "user"],
    ["a password without a user", { host: "h", database: "d", password: "p" }, "Database connector password requires user/username when building a connection_string.", "password"],
    ["a password with a blank user", { host: "h", database: "d", user: "  ", password: "p" }, "requires user/username", "password"],
    ["a non-integer port", { host: "h", database: "d", port: "abc" }, "Database connector port must be an integer when provided.", "port"],
    ["a fractional port", { host: "h", database: "d", port: 12.5 }, "port must be an integer", "port"],
  ])("rejects %s", (_label, source, message, field) => {
    const error = expectValidationError(() => runtimeSqlConnectionString("postgres", source), "invalid_sql_descriptor", message);
    expect(error.details).toEqual({ field, provider: "postgres" });
  });

  // "constructor" is an inherited Object.prototype name; the own-key guard must not treat it as a scheme.
  it.each<[string, Record<string, unknown>]>([
    ["postgres", { host: "h" }],
    ["postgres", { host: "  ", database: "d" }],
    ["oracle", {}],
    ["constructor", { host: "h", database: "d" }],
    ["sql", {}],
  ])("requires connection_string for %s with %j", (provider, source) => {
    const error = expectValidationError(
      () => runtimeSqlConnectionString(provider, source),
      "missing_connection_string",
      "require connection_string or a structured host/database descriptor",
    );
    expect(error.details).toEqual({ provider });
  });

  it("builds a sqlite DSN from a resolved path", () => {
    expect(runtimeSqlConnectionString("sqlite", { path: " ./data/app.db " })).toBe(
      `sqlite+pysqlite:///${resolvePath("./data/app.db")}`,
    );
  });

  it("requires a sqlite path", () => {
    const error = expectValidationError(
      () => runtimeSqlConnectionString("sqlite", { path: "  " }),
      "missing_connection_string",
      "SQLite API descriptors require path or connection_string.",
    );
    expect(error.details).toEqual({ provider: "sqlite" });
  });
});

describe("runtimeSqlQuery", () => {
  it.each<[Record<string, unknown>, string]>([
    [{ query: " select 1 " }, "select 1"],
    [{ query: "  ", table: "orders" }, "SELECT * FROM orders"],
    [{ table: "orders" }, "SELECT * FROM orders"],
    [{ table: "orders", schema: null }, "SELECT * FROM orders"],
    [{ table: " orders ", schema: "public" }, "SELECT * FROM public.orders"],
  ])("builds %j", (source, expected) => {
    expect(runtimeSqlQuery(source)).toBe(expected);
  });

  it("requires a table when no query is given", () => {
    expectValidationError(() => runtimeSqlQuery({}), "invalid_sql_descriptor", "non-empty table");
  });

  it("rejects complex table and schema identifiers", () => {
    expectValidationError(() => runtimeSqlQuery({ table: "bad-name" }), "invalid_sql_identifier", "simple schema/table identifiers");
    const error = expectValidationError(
      () => runtimeSqlQuery({ table: "orders", schema: "pub lic" }),
      "invalid_sql_identifier",
      "simple schema/table identifiers",
    );
    expect(error.details).toEqual({ field: "schema", value: "pub lic" });
  });
});

describe("runtimeRestUrl", () => {
  it.each<[Record<string, unknown>, string]>([
    [{ url: " https://a/b " }, "https://a/b"],
    [{ base_url: "https://a//", path: "//v1/items" }, "https://a/v1/items"],
    [{ base_url: "https://a/" }, "https://a"],
    [{ base_url: "https://a", path: "  " }, "https://a"],
    [{ url: "  ", base_url: "https://a", path: "v1" }, "https://a/v1"],
  ])("resolves %j", (source, expected) => {
    expect(runtimeRestUrl(source)).toBe(expected);
  });

  it.each<[Record<string, unknown>]>([[{}], [{ base_url: 5 }], [{ base_url: "  " }]])("requires url or base_url for %j", source => {
    expectValidationError(() => runtimeRestUrl(source), "missing_rest_url", "API and self_hosted REST descriptors require url or base_url.");
  });
});

describe("normalizeRuntimeConnection", () => {
  it.each<[string, Record<string, unknown>, Record<string, unknown>]>([
    ["csv with a path", { type: "csv", path: "/x.csv", delimiter: ";" }, { type: "file", file_type: "csv", file_path: "/x.csv", delimiter: ";" }],
    ["xlsx via file_path with a sheet", { type: "XLSX", file_path: "/x.xlsx", sheet: "S1" }, { type: "file", file_type: "excel", file_path: "/x.xlsx", sheet: "S1" }],
    ["the connection_type alias", { connection_type: "rest", url: "https://u" }, { connection_type: "rest", type: "rest_api", url: "https://u" }],
    ["an envelope location", { type: "csv", location: { path: "/x.csv" } }, { type: "file", file_type: "csv", file_path: "/x.csv" }],
    ["inline csv", { type: "csv", csv: "a,b\n1,2" }, { type: "file", file_type: "csv", content: "a,b\n1,2" }],
    ["inline tsv", { type: "tsv", csv: "a\tb" }, { type: "file", file_type: "tsv", content: "a\tb" }],
    ["inline json", { type: "json", json_str: "[]" }, { type: "file", file_type: "json", content: "[]" }],
    ["inline excel", { type: "xls", excel_b64: "QUJD" }, { type: "file", file_type: "excel", content: "QUJD" }],
    ["inline parquet", { type: "parquet", parquet_b64: "QUJD" }, { type: "file", file_type: "parquet", content: "QUJD" }],
    // base_url is folded into url and dropped; path stays alongside, as in the Python SDK.
    ["rest with base_url and path", { type: "rest", base_url: "https://api.x/", path: "/v1" }, { type: "rest_api", url: "https://api.x/v1", path: "/v1" }],
    ["api with url", { type: "api", url: "https://u" }, { type: "rest_api", url: "https://u" }],
    ["s3 with format", { type: "s3", bucket: "b", format: "parquet" }, { type: "s3", bucket: "b", file_type: "parquet" }],
    ["gcs keeping an explicit file_type", { type: "gcs", format: "csv", file_type: "json" }, { type: "gcs", format: "csv", file_type: "json" }],
    ["azure_blob without format", { type: "azure_blob", container: "c" }, { type: "azure_blob", container: "c" }],
    [
      "a postgres descriptor",
      { type: "postgres", host: "h", database: "d", table: "t", port: 5433, user: "u", password: "p" },
      { type: "sql", provider: "postgres", connection_string: "postgresql://u:p@h:5433/d", query: "SELECT * FROM t", table: "t" },
    ],
    [
      "a generic sql descriptor with a provider",
      { type: "sql", provider: "MySQL", host: "h", database: "d", username: "u", query: "select 1" },
      { type: "sql", provider: "mysql", connection_string: "mysql://u@h:3306/d", query: "select 1" },
    ],
    [
      "a generic sql descriptor with a connection string",
      { type: "sql", connection_string: "postgresql://x", table: "t" },
      { type: "sql", connection_string: "postgresql://x", query: "SELECT * FROM t", table: "t" },
    ],
    [
      "a sqlite descriptor",
      { type: "sqlite", path: "/db.sqlite", table: "t" },
      {
        type: "sql",
        provider: "sqlite",
        path: "/db.sqlite",
        connection_string: `sqlite+pysqlite:///${resolvePath("/db.sqlite")}`,
        query: "SELECT * FROM t",
        table: "t",
      },
    ],
    ["an unknown connector type", { type: "kafka", topic: "t", extra: undefined }, { type: "kafka", topic: "t" }],
    ["an already canonical rest_api type", { type: "rest_api", url: "https://u", base_url: "https://b" }, { type: "rest_api", url: "https://u", base_url: "https://b" }],
  ])("normalizes %s", (_label, source, expected) => {
    expect(normalizeRuntimeConnection(source)).toEqual(expected);
  });

  it.each<[Record<string, unknown>, string]>([
    [{ type: "csv" }, "csv"],
    [{ type: "json", csv: "x" }, "json"],
    [{ type: "xlsx", parquet_b64: "x" }, "excel"],
  ])("rejects file connector %j without matching content", (source, fileType) => {
    const error = expectValidationError(
      () => normalizeRuntimeConnection(source),
      "invalid_file_connector",
      "File connectors require a local path or inline content matching their declared type.",
    );
    expect(error.details).toEqual({ type: fileType });
  });

  it("propagates SQL and REST descriptor errors", () => {
    expectValidationError(() => normalizeRuntimeConnection({ type: "sql" }), "missing_connection_string", "connection_string");
    expectValidationError(() => normalizeRuntimeConnection({ type: "rest" }), "missing_rest_url", "url or base_url");
  });

  it.each<[Record<string, unknown>]>([[{}], [{ type: "  " }], [{ url: "https://u" }]])("requires a connector type for %j", source => {
    expectValidationError(
      () => normalizeRuntimeConnection(source),
      "missing_connection_type",
      "require an explicit connector type or a direct source payload.",
    );
  });
});

describe("normalizeApiSourcePayload", () => {
  it.each<[string, Record<string, unknown>, string | undefined, Record<string, unknown>]>([
    [
      "a payload with a connection object",
      { name: "orders", connection: { type: "csv", path: "/x.csv" } },
      undefined,
      { name: "orders", connection: { type: "file", file_type: "csv", file_path: "/x.csv" } },
    ],
    ["direct source keys", { records: [{ a: 1 }] }, undefined, { records: [{ a: 1 }], name: "source_0" }],
    [
      "direct keys with a non-object connection",
      { dataset_id: "d", connection: "weird" },
      "given",
      { dataset_id: "d", connection: "weird", name: "given" },
    ],
    [
      "a bare connector descriptor",
      { type: "csv", path: "/data/orders.csv" },
      undefined,
      { name: "orders", connection: { type: "file", file_type: "csv", file_path: "/data/orders.csv" } },
    ],
    [
      "a canonical file envelope with an explicit name",
      { type: "csv", location: { path: "/data/orders.csv" } },
      " Custom ",
      { name: "Custom", connection: { type: "file", file_type: "csv", file_path: "/data/orders.csv" } },
    ],
    // `url` is itself a direct source key, so a flattened REST envelope is not re-wrapped.
    [
      "a canonical REST envelope whose url counts as a direct key",
      { type: "rest", location: { url: "https://u" } },
      undefined,
      { type: "rest", url: "https://u", name: "source_0" },
    ],
  ])("normalizes %s", (_label, source, explicitName, expected) => {
    expect(normalizeApiSourcePayload(source, explicitName)).toEqual(expected);
  });
});

describe("CSV header helpers", () => {
  it("canonicalizes blank and duplicate headers", () => {
    expect(canonicalizeCsvHeaders(["a", "", " a ", "a", " "])).toEqual([
      "a",
      "Unnamed_Column",
      "a__2",
      "a__3",
      "Unnamed_Column__2",
    ]);
  });

  it.each<[string, string]>([
    ["a__2", "a"],
    ["a", "a"],
    ["a__b__c", "a"],
    ["", ""],
  ])("baseHeaderName(%j) is %j", (field, expected) => {
    expect(baseHeaderName(field)).toBe(expected);
  });

  it("tokenizes lowercase alphanumeric runs", () => {
    expect(csvFieldTokens("Order ID (excl. tax)")).toEqual(new Set(["order", "id", "excl", "tax"]));
    expect(csvFieldTokens("---")).toEqual(new Set());
  });

  it.each<[string, boolean]>([
    ["Zip", true],
    ["Postal Code", true],
    ["Serial No", true],
    ["SKU", true],
    ["Customer_ID", true],
    ["Payout reference ID", true],
    ["Part Number", true],
    ["Part Code", true],
    ["Part", false],
    ["Invoice", true],
    ["Invoice Amount", false],
    ["Account", true],
    ["Order", true],
    ["Order Total", false],
    ["Code", true],
    ["Code Rate", false],
    ["Number", true],
    ["Number of Days", false],
    ["Item", true],
    ["Item Price", false],
    ["Revenue", false],
    ["---", false],
  ])("csvIsIdentifierField(%j) is %j", (field, expected) => {
    expect(csvIsIdentifierField(field)).toBe(expected);
  });
});

describe("coerceCsvScalar", () => {
  it.each<[string, unknown, unknown]>([
    ["Sales", null, ""],
    ["Sales", undefined, ""],
    ["Sales", true, true],
    ["Sales", 3, 3],
    ["Sales", "   ", ""],
    ["Sales", "1234567890123456", "1234567890123456"],
    ["Sales", "0123", "0123"],
    ["Sales", "-0123", "-0123"],
    ["Order ID", "42", "42"],
    ["Order ID", "1,001", "1,001"],
    ["Order ID", "50%", "50%"],
    ["Sales", "1,234", 1234],
    ["Sales", "(1,234)", -1234],
    ["Sales", "$1,234.50", 1234.5],
    ["Sales", "( \u20ac10.5 )", -10.5],
    ["Sales", "12.5%", "12.5%"],
    ["Sales", "3.14", 3.14],
    ["Sales", "1e3", 1000],
    ["Sales", "+5", 5],
    ["Sales", ".5", 0.5],
    ["Sales", "abc", "abc"],
    ["Sales", "$-", "$-"],
    ["Sales", "(abc)", "(abc)"],
  ])("coerces %s value %j to %j", (field, value, expected) => {
    expect(coerceCsvScalar(field, value)).toBe(expected);
  });
});

describe("looksLikeHeaderAliasRow", () => {
  const HEADERS = ["Store Name", "Sales Total", "Region Name"];

  it("needs at least three columns", () => {
    expect(looksLikeHeaderAliasRow(["Order ID", "Store Name"], ["order id", "store name"])).toBe(false);
  });

  it("detects a row that restates the headers", () => {
    expect(looksLikeHeaderAliasRow(["Order ID", "Store Name", "Sales Total"], ["order id", "store name", "sales total"])).toBe(true);
  });

  it("treats digits under an identifier column as data, not an alias", () => {
    expect(looksLikeHeaderAliasRow(["Order ID", "Store Name", "Sales Total"], ["ORD-1001", "store name", "sales total"])).toBe(false);
  });

  it("rejects values unrelated to the headers", () => {
    expect(looksLikeHeaderAliasRow(HEADERS, ["Synthetic Store 001", "3/1/26", "abc"])).toBe(false);
  });

  it("rejects a high match ratio with a low average overlap", () => {
    expect(looksLikeHeaderAliasRow(HEADERS, ["store name a b c", "sales total a b c", "region name a b c"])).toBe(false);
  });

  it("rejects a high average overlap when too few columns match", () => {
    expect(
      looksLikeHeaderAliasRow(
        [...HEADERS, "Unit Price", "Tax Amount"],
        ["store name", "sales total", "region a b c d", "unit a b c d", "tax a b c d"],
      ),
    ).toBe(false);
  });

  it("skips blank, token-less and header-less cells and requires enough comparable columns", () => {
    expect(looksLikeHeaderAliasRow(HEADERS, ["", "---", "region name"])).toBe(false);
    expect(looksLikeHeaderAliasRow(["###", "Store Name", "Sales Total"], ["x", "store name", "sales total"])).toBe(false);
    expect(looksLikeHeaderAliasRow(HEADERS, ["store name"])).toBe(false);
  });
});
