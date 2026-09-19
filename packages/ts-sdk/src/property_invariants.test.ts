// SPDX-License-Identifier: Apache-2.0
// Property-based invariants (fast-check) over the SDK's pure helpers.
//
// Every property below is a contract the rest of the SDK -- or the Python SDK, where noted --
// already depends on: canonical-JSON + sha256 parity, CSV parse round-trips, aggregation
// arithmetic, SQL DSN provider lookup, error-envelope totality, the HTTP status -> error-class
// mapping, base-URL normalization, Algenta-owned host classification and device-id validation.
// Each property runs at most 100 generated cases; nothing here touches the network, timers or
// the disk.
import * as fc from "fast-check";
import { describe, expect, it } from "vitest";

import {
  base64UrlDecode,
  base64UrlEncode,
  canonicalJson,
  normalizeText,
  stableHash,
  stableStringify,
  stripNullEntries,
} from "./_runtime_helpers_a.js";
import {
  CANONICAL_AGGREGATIONS,
  canonicalizeAggregation,
  dedupeStrings,
  isNullishFilterValue,
  numericValue,
  orderedFields,
  valuesEqual,
} from "./_runtime_helpers_b.js";
import {
  baseHeaderName,
  canonicalizeCsvHeaders,
  coerceCsvScalar,
  runtimeSqlConnectionString,
  sqlIdentifier,
  stripUndefined,
} from "./_runtime_helpers_c.js";
import { aggregateValues, parseCsvRows, parseCsvText } from "./_runtime_helpers_d.js";
import { RuntimeValidationError, extractRuntimeValidationErrors } from "./_runtime_errors.js";
import {
  AuthenticationError,
  DecisionEngineClient,
  DecisionEngineError,
  NotFoundError,
  RateLimitError,
  ServerError,
  ValidationError,
  extractResponseError,
  normalizedErrorCode,
  normalizedErrorMessage,
} from "./client.js";
import {
  DEVICE_ID_HEADER,
  SDK_VERSION_HEADER,
  resolveClientDeviceHeaders,
} from "./client_device_headers.js";
import { ALGENTA_OWNED_HOSTS, ALGENTA_OWNED_SUFFIXES } from "./contract.js";
import { isAlgentaOwnedBaseUrl, normalizeBaseUrl } from "./privacy_profile.js";

const RUNS = { numRuns: 100 };

// ---------------------------------------------------------------------------------------------
// Shared arbitraries and oracles
// ---------------------------------------------------------------------------------------------

// An own `__proto__` key is a JS-engine quirk (assigning it on a fresh `{}` rewrites the
// prototype instead of creating an entry), not a payload shape the engine ever emits, so it is
// excluded from every generated object below.
function hasOnlySafeKeys(value: unknown): boolean {
  if (Array.isArray(value)) {
    return value.every(hasOnlySafeKeys);
  }
  if (value !== null && typeof value === "object") {
    return Object.entries(value as Record<string, unknown>).every(
      ([key, item]) => key !== "__proto__" && hasOnlySafeKeys(item),
    );
  }
  return true;
}

const jsonArb = fc.jsonValue().filter(hasOnlySafeKeys);
const anythingArb = fc.anything().filter(hasOnlySafeKeys);
const safeKeyArb = fc.string().filter((key) => key !== "__proto__");
const padArb = fc.constantFrom("", " ", "  ", "\t");

// Every name a plain `{}` answers `in` / `[]` for without owning it: the Object.prototype
// members, plus "prototype" (owned by any Function-valued entry). A lookup table keyed by
// caller text must reject all of them or it hands back an inherited function instead of
// throwing -- the HIGH finding of codna review on thyn-ai/algenta-sdk#70.
const INHERITED_NAMES = [
  "constructor",
  "toString",
  "toLocaleString",
  "valueOf",
  "hasOwnProperty",
  "isPrototypeOf",
  "propertyIsEnumerable",
  "__proto__",
  "__defineGetter__",
  "__defineSetter__",
  "__lookupGetter__",
  "__lookupSetter__",
  "prototype",
] as const;

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

function hasOwn(record: object, key: string): boolean {
  return Object.prototype.hasOwnProperty.call(record, key);
}

function captureError(run: () => unknown): unknown {
  try {
    run();
    return null;
  } catch (err) {
    return err;
  }
}

function reverseKeyOrder(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map(reverseKeyOrder);
  }
  if (value !== null && typeof value === "object") {
    const record = value as Record<string, unknown>;
    const output: Record<string, unknown> = {};
    for (const key of Object.keys(record).reverse()) {
      output[key] = reverseKeyOrder(record[key]);
    }
    return output;
  }
  return value;
}

function containsNonFinite(value: unknown): boolean {
  if (typeof value === "number") {
    return !Number.isFinite(value);
  }
  if (Array.isArray(value)) {
    return value.some(containsNonFinite);
  }
  if (value !== null && typeof value === "object") {
    return Object.values(value as Record<string, unknown>).some(containsNonFinite);
  }
  return false;
}

function hasNoNullishObjectEntries(value: unknown): boolean {
  if (Array.isArray(value)) {
    return value.every(hasNoNullishObjectEntries);
  }
  if (value !== null && typeof value === "object") {
    return Object.values(value as Record<string, unknown>).every(
      (item) => item !== null && item !== undefined && hasNoNullishObjectEntries(item),
    );
  }
  return true;
}

// ---------------------------------------------------------------------------------------------
// Canonical JSON + hashing: the cross-language plan_hash / intent_signature contract
// ---------------------------------------------------------------------------------------------

describe("canonical JSON and hashing (_runtime_helpers_a)", () => {
  it("canonicalJson parses back to its input, is ASCII-only and independent of key order", () => {
    fc.assert(
      fc.property(jsonArb, (value) => {
        const canonical = canonicalJson(value);
        expect(JSON.parse(canonical)).toEqual(JSON.parse(JSON.stringify(value)));
        expect([...canonical].every((char) => char.charCodeAt(0) < 0x80)).toBe(true);
        expect(canonicalJson(reverseKeyOrder(value))).toBe(canonical);
      }),
      RUNS,
    );
  });

  it("canonicalJson is total: it throws TypeError exactly when a non-finite number is present", () => {
    fc.assert(
      fc.property(anythingArb, (value) => {
        if (containsNonFinite(value)) {
          expect(() => canonicalJson(value)).toThrow(TypeError);
          return;
        }
        const canonical = canonicalJson(value);
        expect(() => JSON.parse(canonical)).not.toThrow();
      }),
      RUNS,
    );
  });

  it("stableStringify and canonicalJson encode the same value", () => {
    fc.assert(
      fc.property(jsonArb, (value) => {
        expect(JSON.parse(stableStringify(value))).toEqual(JSON.parse(canonicalJson(value)));
      }),
      RUNS,
    );
  });

  it("stripNullEntries is idempotent, leaves no null entries, and a null key hashes like an absent key", () => {
    fc.assert(
      fc.property(fc.dictionary(safeKeyArb, jsonArb), safeKeyArb, (record, extraKey) => {
        fc.pre(!hasOwn(record, extraKey));
        const stripped = stripNullEntries(record);
        expect(stripNullEntries(stripped)).toEqual(stripped);
        expect(hasNoNullishObjectEntries(stripped)).toBe(true);
        const withNullKey = stripNullEntries({ ...record, [extraKey]: null });
        expect(withNullKey).toEqual(stripped);
        expect(stableHash(withNullKey)).toBe(stableHash(stripped));
      }),
      RUNS,
    );
  });

  it("stableHash is a 64-hex sha256 digest that ignores key order", () => {
    fc.assert(
      fc.property(jsonArb, (value) => {
        const digest = stableHash(value);
        expect(digest).toMatch(/^[0-9a-f]{64}$/);
        expect(stableHash(reverseKeyOrder(value))).toBe(digest);
      }),
      RUNS,
    );
  });

  it("base64url encode/decode round-trips arbitrary bytes without padding or unsafe characters", () => {
    fc.assert(
      fc.property(fc.uint8Array({ maxLength: 256 }), (bytes) => {
        const input = Buffer.from(bytes);
        const encoded = base64UrlEncode(input);
        expect(encoded).toMatch(/^[A-Za-z0-9_-]*$/);
        expect(base64UrlDecode(encoded).equals(input)).toBe(true);
      }),
      RUNS,
    );
  });

  it("normalizeText is idempotent, ASCII-case-insensitive and emits single-spaced [a-z0-9] words", () => {
    fc.assert(
      fc.property(fc.string({ unit: "binary" }), (text) => {
        const normalized = normalizeText(text);
        expect(normalized).toMatch(/^(?:[a-z0-9]+(?: [a-z0-9]+)*)?$/);
        expect(normalizeText(normalized)).toBe(normalized);
      }),
      RUNS,
    );
    fc.assert(
      fc.property(fc.string(), (text) => {
        expect(normalizeText(text.toUpperCase())).toBe(normalizeText(text));
      }),
      RUNS,
    );
  });
});

// ---------------------------------------------------------------------------------------------
// Aggregations and value semantics: shared verbatim with the Python SDK
// ---------------------------------------------------------------------------------------------

describe("aggregation and value semantics (_runtime_helpers_b, _runtime_helpers_d)", () => {
  const AGGREGATION_SPELLINGS: Readonly<Record<string, string>> = {
    sum: "sum",
    total: "sum",
    avg: "avg",
    average: "avg",
    mean: "avg",
    count: "count",
    min: "min",
    minimum: "min",
    max: "max",
    maximum: "max",
  };
  const spellingArb = fc.constantFrom(...Object.keys(AGGREGATION_SPELLINGS));
  const mixCase = (word: string, flags: boolean[]): string =>
    [...word].map((char, index) => (flags[index % flags.length] ? char.toUpperCase() : char)).join("");

  it("canonicalizeAggregation maps every alias, in any case and padding, to a canonical name and is idempotent", () => {
    fc.assert(
      fc.property(
        spellingArb,
        fc.array(fc.boolean(), { minLength: 1, maxLength: 8 }),
        padArb,
        padArb,
        (spelling, flags, lead, trail) => {
          const canonical = canonicalizeAggregation(`${lead}${mixCase(spelling, flags)}${trail}`);
          expect(canonical).toBe(AGGREGATION_SPELLINGS[spelling]);
          expect(CANONICAL_AGGREGATIONS).toContain(canonical);
          expect(canonicalizeAggregation(canonical)).toBe(canonical);
        },
      ),
      RUNS,
    );
  });

  it("canonicalizeAggregation never falls back silently: unknown spellings throw invalid_aggregation", () => {
    // Own-key precondition (`hasOwn`, never `in`, which walks the prototype chain), with the
    // inherited names mixed into the generator so every run samples them.
    const unknownArb = fc
      .oneof(fc.string(), fc.constantFrom(...INHERITED_NAMES))
      .filter((text) => !hasOwn(AGGREGATION_SPELLINGS, text.trim().toLowerCase()));
    fc.assert(
      fc.property(unknownArb, (spelling) => {
        const thrown = captureError(() => canonicalizeAggregation(spelling));
        expect(thrown).toBeInstanceOf(RuntimeValidationError);
        const error = thrown as RuntimeValidationError;
        expect(error.code).toBe("invalid_aggregation");
        expect(error.details.supported).toEqual([...CANONICAL_AGGREGATIONS].sort());
      }),
      RUNS,
    );
  });

  it("canonicalizeAggregation rejects Object.prototype names in any case and padding, so they never reach aggregateValues", () => {
    const supported = [...CANONICAL_AGGREGATIONS].sort();
    for (const name of INHERITED_NAMES) {
      const spellings = [name, ` ${name} `, `\t${name}\t`, name.toUpperCase(), mixCase(name, [true, false])];
      for (const spelling of spellings) {
        const thrown = captureError(() => canonicalizeAggregation(spelling));
        expect(thrown).toBeInstanceOf(RuntimeValidationError);
        const error = thrown as RuntimeValidationError;
        expect(error.code).toBe("invalid_aggregation");
        expect(error.message).toBe(`Unknown aggregation '${spelling}'. Supported: ${supported.join(", ")}.`);
        expect(error.details).toEqual({ aggregation: spelling, supported });
        expect(captureError(() => aggregateValues([1, 2, 3], spelling))).toBeInstanceOf(RuntimeValidationError);
      }
    }
  });

  it("aggregateValues: count is the length, sum is exact, min <= avg <= max, and aliases agree", () => {
    const integersArb = fc.array(fc.integer({ min: -1_000_000_000, max: 1_000_000_000 }), {
      maxLength: 40,
    });
    fc.assert(
      fc.property(integersArb, spellingArb, (values, spelling) => {
        expect(aggregateValues(values, spelling)).toBe(
          aggregateValues(values, canonicalizeAggregation(spelling)),
        );
        const sum = values.reduce((acc, value) => acc + value, 0);
        expect(aggregateValues(values, "count")).toBe(values.length);
        expect(aggregateValues(values, "sum")).toBe(sum);
        if (values.length === 0) {
          expect(aggregateValues(values, "avg")).toBeNull();
          expect(aggregateValues(values, "min")).toBeNull();
          expect(aggregateValues(values, "max")).toBeNull();
          return;
        }
        const min = aggregateValues(values, "min") as number;
        const avg = aggregateValues(values, "avg") as number;
        const max = aggregateValues(values, "max") as number;
        expect(min).toBe(Math.min(...values));
        expect(max).toBe(Math.max(...values));
        expect(avg).toBe(sum / values.length);
        expect(min <= avg && avg <= max).toBe(true);
      }),
      RUNS,
    );
  });

  it("numericValue round-trips finite doubles (as numbers and as strings) and is otherwise null", () => {
    fc.assert(
      fc.property(fc.double({ noNaN: true, noDefaultInfinity: true }), (x) => {
        expect(numericValue(x) === x).toBe(true);
        expect(numericValue(String(x)) === x).toBe(true);
        expect(numericValue(`  ${String(x)}\t`) === x).toBe(true);
      }),
      RUNS,
    );
    fc.assert(
      fc.property(anythingArb, (value) => {
        const parsed = numericValue(value);
        expect(parsed === null || Number.isFinite(parsed)).toBe(true);
        if (typeof value === "number" && !Number.isFinite(value)) {
          expect(parsed).toBeNull();
        }
      }),
      RUNS,
    );
  });

  it("valuesEqual is reflexive on non-nullish scalars, symmetric, and ASCII-case-insensitive", () => {
    const scalarArb = fc.oneof(
      fc.string(),
      fc.string({ unit: "binary" }),
      fc.integer(),
      fc.double(),
      fc.boolean(),
      fc.constant(null),
      fc.constant(undefined),
    );
    fc.assert(
      fc.property(scalarArb, (value) => {
        fc.pre(!isNullishFilterValue(value));
        expect(valuesEqual(value, value)).toBe(true);
      }),
      RUNS,
    );
    fc.assert(
      fc.property(scalarArb, scalarArb, (left, right) => {
        expect(valuesEqual(left, right)).toBe(valuesEqual(right, left));
      }),
      RUNS,
    );
    fc.assert(
      fc.property(fc.string(), (text) => {
        fc.pre(!isNullishFilterValue(text));
        expect(valuesEqual(text, text.toUpperCase())).toBe(true);
      }),
      RUNS,
    );
  });

  it("dedupeStrings trims, drops blanks and repeats, keeps first-seen order, and is idempotent", () => {
    const rawArb = fc.array(fc.oneof(fc.string(), fc.string().map((text) => `  ${text} `)), {
      maxLength: 20,
    });
    fc.assert(
      fc.property(rawArb, (values) => {
        const deduped = dedupeStrings(values);
        expect(deduped).toEqual([...new Set(values.map((value) => value.trim()).filter(Boolean))]);
        expect(dedupeStrings(deduped)).toEqual(deduped);
        expect(dedupeStrings([...values, ...values])).toEqual(deduped);
      }),
      RUNS,
    );
  });

  it("orderedFields lists each key once in first-seen order, and later records never reorder it", () => {
    const recordsArb = fc.array(fc.dictionary(safeKeyArb, jsonArb, { maxKeys: 5 }), { maxLength: 8 });
    fc.assert(
      fc.property(recordsArb, fc.nat({ max: 8 }), (records, cut) => {
        const fields = orderedFields(records);
        expect(new Set(fields).size).toBe(fields.length);
        expect(new Set(fields)).toEqual(new Set(records.flatMap((record) => Object.keys(record))));
        expect(orderedFields([...records, ...records])).toEqual(fields);
        const prefix = orderedFields(records.slice(0, cut));
        expect(fields.slice(0, prefix.length)).toEqual(prefix);
      }),
      RUNS,
    );
  });
});

// ---------------------------------------------------------------------------------------------
// CSV parsing and coercion: the local-runtime ingestion path
// ---------------------------------------------------------------------------------------------

describe("CSV parsing and coercion (_runtime_helpers_c, _runtime_helpers_d)", () => {
  const csvCellArb = fc.oneof(
    fc.string(),
    fc.string({ unit: fc.constantFrom("a", "Z", "0", " ", ",", '"', "\n", "\r"), maxLength: 12 }),
  );
  // parseCsvRows drops a line that is a single empty cell (blank line), so never generate one.
  const csvRowArb = fc
    .array(csvCellArb, { minLength: 1, maxLength: 6 })
    .filter((row) => row.length > 1 || row[0].length > 0);
  const csvRowsArb = fc.array(csvRowArb, { minLength: 1, maxLength: 8 });
  const quoteCell = (cell: string): string =>
    /[",\r\n]/.test(cell) ? `"${cell.replace(/"/g, '""')}"` : cell;
  const serializeCsv = (rows: string[][], terminator: string, trailing: boolean): string =>
    rows.map((row) => row.map(quoteCell).join(",")).join(terminator) + (trailing ? terminator : "");
  const headerArb = fc.stringMatching(/^[a-z][a-z_]{0,10}$/).filter((header) => !header.includes("__"));

  it("parseCsvRows inverts RFC 4180 quoting under every line terminator", () => {
    fc.assert(
      fc.property(
        csvRowsArb,
        fc.constantFrom("\n", "\r\n", "\r"),
        fc.boolean(),
        (rows, terminator, trailing) => {
          expect(parseCsvRows(serializeCsv(rows, terminator, trailing))).toEqual(rows);
        },
      ),
      RUNS,
    );
  });

  it("canonicalizeCsvHeaders keeps length and first occurrences, suffixes repeats uniquely, and is idempotent", () => {
    const headersArb = fc.array(fc.oneof(headerArb, fc.constant(""), fc.constant("  ")), {
      maxLength: 10,
    });
    fc.assert(
      fc.property(headersArb, (headers) => {
        const canonical = canonicalizeCsvHeaders(headers);
        expect(canonical).toHaveLength(headers.length);
        expect(new Set(canonical).size).toBe(canonical.length);
        expect(canonicalizeCsvHeaders(canonical)).toEqual(canonical);
        const seen = new Set<string>();
        headers.forEach((header, index) => {
          const base = header.trim() || "Unnamed_Column";
          expect(baseHeaderName(canonical[index])).toBe(base);
          if (!seen.has(base)) {
            expect(canonical[index]).toBe(base);
          }
          seen.add(base);
        });
      }),
      RUNS,
    );
  });

  it("coerceCsvScalar reads accounting/currency/grouped integers on measures, keeps identifiers verbatim, never throws", () => {
    const grouped = (n: number): string => String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 999_999_999 }),
        fc.constantFrom("", "$", "£", "€", "¥"),
        fc.boolean(),
        fc.boolean(),
        (n, currency, group, negative) => {
          const digits = group ? grouped(n) : String(n);
          const raw = negative ? `(${currency}${digits})` : `${currency}${digits}`;
          expect(coerceCsvScalar("amount", raw)).toBe(negative ? -n : n);
        },
      ),
      RUNS,
    );
    fc.assert(
      fc.property(
        fc.constantFrom("id", "customer_id", "sku", "zip_code", "part_number", "uuid", "serial"),
        fc.integer({ min: 0, max: 999_999_999 }),
        fc.boolean(),
        (field, n, zeroPad) => {
          const raw = zeroPad ? String(n).padStart(6, "0") : String(n);
          expect(coerceCsvScalar(field, raw)).toBe(raw);
        },
      ),
      RUNS,
    );
    // Cells are scalars (parseCsvText only ever passes strings), so totality is claimed over
    // scalars: an object whose own `toString` is not callable makes String(value) throw at the
    // language level, which is not a coercion contract this helper can or should own.
    const cellScalarArb = fc.oneof(
      fc.string(),
      fc.string({ unit: "binary" }),
      fc.integer(),
      fc.double(),
      fc.boolean(),
      fc.constant(null),
      fc.constant(undefined),
    );
    fc.assert(
      fc.property(fc.string(), cellScalarArb, (field, value) => {
        const coerced = coerceCsvScalar(field, value);
        expect(["string", "number", "boolean"]).toContain(typeof coerced);
        if (value === null || value === undefined) {
          expect(coerced).toBe("");
        }
      }),
      RUNS,
    );
  });

  it("parseCsvText composes parseCsvRows, canonicalizeCsvHeaders and coerceCsvScalar: one record per data row", () => {
    const numericCellArb = fc.oneof(
      fc.integer().map(String),
      fc.double({ noNaN: true, noDefaultInfinity: true }).map(String),
    );
    const tableArb = fc.array(headerArb, { minLength: 1, maxLength: 5 }).chain((headers) =>
      fc.tuple(
        fc.constant(headers),
        fc.array(fc.array(numericCellArb, { minLength: headers.length, maxLength: headers.length }), {
          minLength: 1,
          maxLength: 8,
        }),
      ),
    );
    fc.assert(
      fc.property(tableArb, fc.constantFrom("\n", "\r\n"), ([headers, rows], terminator) => {
        const text = [headers.join(","), ...rows.map((row) => row.join(","))].join(terminator);
        const records = parseCsvText(text);
        const canonical = canonicalizeCsvHeaders(headers);
        expect(records).toHaveLength(rows.length);
        records.forEach((record, rowIndex) => {
          expect(Object.keys(record)).toEqual(canonical);
          canonical.forEach((header, column) => {
            expect(record[header]).toBe(coerceCsvScalar(header, rows[rowIndex][column]));
          });
        });
      }),
      RUNS,
    );
  });

  it("sqlIdentifier trims simple identifiers and rejects everything else with a typed RuntimeValidationError", () => {
    const identifierRe = /^[A-Za-z_][A-Za-z0-9_$]*$/;
    fc.assert(
      fc.property(
        fc.stringMatching(/^[A-Za-z_][A-Za-z0-9_$]{0,20}$/),
        padArb,
        padArb,
        (identifier, lead, trail) => {
          expect(sqlIdentifier(`${lead}${identifier}${trail}`, "table")).toBe(identifier);
        },
      ),
      RUNS,
    );
    fc.assert(
      fc.property(
        fc.oneof(jsonArb, fc.constant(undefined), fc.string({ unit: "binary" })),
        (value) => {
          const trimmed = typeof value === "string" ? value.trim() : "";
          const thrown = captureError(() => sqlIdentifier(value, "table"));
          if (trimmed.length > 0 && identifierRe.test(trimmed)) {
            expect(thrown).toBeNull();
            return;
          }
          expect(thrown).toBeInstanceOf(RuntimeValidationError);
          expect((thrown as RuntimeValidationError).code).toBe(
            trimmed.length > 0 ? "invalid_sql_identifier" : "invalid_sql_descriptor",
          );
        },
      ),
      RUNS,
    );
  });

  it("stripUndefined drops exactly the null/undefined entries and keeps the rest by identity", () => {
    fc.assert(
      fc.property(fc.dictionary(safeKeyArb, fc.oneof(jsonArb, fc.constant(undefined))), (record) => {
        const stripped = stripUndefined(record);
        for (const [key, value] of Object.entries(record)) {
          if (value === null || value === undefined) {
            expect(hasOwn(stripped, key)).toBe(false);
          } else {
            expect(stripped[key]).toBe(value);
          }
        }
        expect(Object.keys(stripped)).toEqual(
          Object.keys(record).filter((key) => record[key] !== null && record[key] !== undefined),
        );
        expect(stripUndefined(stripped)).toEqual(stripped);
      }),
      RUNS,
    );
  });
});

// ---------------------------------------------------------------------------------------------
// SQL connection strings: the provider -> DSN scheme table is keyed by caller text
// ---------------------------------------------------------------------------------------------

describe("SQL connection strings (_runtime_helpers_c)", () => {
  // Mirrors _SQL_DSN_SCHEMES in the Python SDK's runtime_connection_sql.py.
  const SQL_SCHEMES: Readonly<Record<string, string>> = {
    postgres: "postgresql",
    postgresql: "postgresql",
    mysql: "mysql",
    mssql: "mssql",
    redshift: "redshift",
  };
  const structured = { host: "db.internal", database: "analytics" };

  it("builds a DSN for every known provider from a structured host/database descriptor", () => {
    for (const [provider, scheme] of Object.entries(SQL_SCHEMES)) {
      expect(runtimeSqlConnectionString(provider, structured)).toMatch(
        new RegExp(`^${scheme}://db\\.internal:\\d+/analytics$`),
      );
    }
  });

  it("rejects every provider the table does not own -- Object.prototype names included -- with missing_connection_string", () => {
    const unknownProviderArb = fc
      .oneof(fc.string(), fc.constantFrom(...INHERITED_NAMES))
      .filter((provider) => !hasOwn(SQL_SCHEMES, provider));
    fc.assert(
      fc.property(unknownProviderArb, (provider) => {
        const thrown = captureError(() => runtimeSqlConnectionString(provider, structured));
        expect(thrown).toBeInstanceOf(RuntimeValidationError);
        const error = thrown as RuntimeValidationError;
        expect(error.code).toBe("missing_connection_string");
        expect(error.details).toEqual({ provider });
      }),
      RUNS,
    );
    for (const provider of INHERITED_NAMES) {
      const thrown = captureError(() => runtimeSqlConnectionString(provider, structured));
      expect(thrown).toBeInstanceOf(RuntimeValidationError);
      expect((thrown as RuntimeValidationError).code).toBe("missing_connection_string");
    }
  });
});

// ---------------------------------------------------------------------------------------------
// Error envelopes and classification: what every SDK caller's catch block relies on
// ---------------------------------------------------------------------------------------------

describe("error envelopes and classification (_client_errors, _runtime_errors)", () => {
  const envelopeArb = fc.record({
    code: fc.string({ minLength: 1 }),
    message: fc.string({ minLength: 1 }),
  });

  it("normalizedErrorCode/Message read the code and message from every accepted envelope shape", () => {
    fc.assert(
      fc.property(
        envelopeArb,
        fc.constantFrom("error", "detail", "detail.error"),
        fc.string({ minLength: 1 }),
        (envelope, shape, fallback) => {
          const body =
            shape === "error"
              ? { error: envelope }
              : shape === "detail"
                ? { detail: envelope }
                : { detail: { error: envelope } };
          expect(extractResponseError(body)).toEqual(envelope);
          expect(normalizedErrorCode(body, fallback)).toBe(envelope.code);
          expect(normalizedErrorMessage(body)).toBe(envelope.message);
        },
      ),
      RUNS,
    );
  });

  it("the envelope readers are total over arbitrary bodies and never yield an empty code or message", () => {
    fc.assert(
      fc.property(fc.oneof(jsonArb, fc.constant(undefined)), fc.string({ minLength: 1 }), (body, fallback) => {
        const envelope = extractResponseError(body);
        expect(envelope === null || isPlainObject(envelope)).toBe(true);
        expect(normalizedErrorCode(body, fallback).length).toBeGreaterThan(0);
        expect(normalizedErrorMessage(body).length).toBeGreaterThan(0);
        if (envelope === null) {
          expect(normalizedErrorCode(body, fallback)).toBe(fallback);
          expect(normalizedErrorMessage(body)).toBe("Unknown error");
        }
      }),
      RUNS,
    );
  });

  it("validation errors surface exactly the plain-object items, in order, from every carrier", () => {
    const itemsArb = fc.array(fc.oneof(jsonArb, fc.constant(undefined)), { maxLength: 6 });
    fc.assert(
      fc.property(itemsArb, fc.string(), fc.integer({ min: 400, max: 599 }), (items, message, status) => {
        const expected = items.filter(isPlainObject);
        expect(extractRuntimeValidationErrors({ validation_errors: items })).toEqual(expected);
        expect(
          new RuntimeValidationError("code", message, { validation_errors: items }).validationErrors,
        ).toEqual(expected);
        expect(
          new RuntimeValidationError("code", message, {
            source_error_details: { validation_errors: items },
          }).validationErrors,
        ).toEqual(expected);
        const direct = new DecisionEngineError(message, status, "validation_error", {
          error: { details: items },
        });
        expect(direct.validationErrors).toEqual(expected);
        const nested = new DecisionEngineError(message, status, "validation_error", {
          detail: { details: { validation_errors: items } },
        });
        expect(nested.validationErrors).toEqual(expected);
        expect(nested.fieldErrors).toEqual(expected);
      }),
      RUNS,
    );
    fc.assert(
      fc.property(anythingArb, (value) => {
        const errors = extractRuntimeValidationErrors(value);
        expect(Array.isArray(errors) && errors.every(isPlainObject)).toBe(true);
      }),
      RUNS,
    );
  });

  it("handleResponse maps every HTTP status to the documented error class carrying the body's code and message", async () => {
    const client = new DecisionEngineClient({
      apiKey: "de_test_123",
      baseUrl: "https://example.test",
      maxRetries: 0,
      timeout: 1_000,
    });
    // 304 is the one status in range that the Response constructor forbids a body for.
    const failingStatusArb = fc.integer({ min: 300, max: 599 }).filter((status) => status !== 304);
    await fc.assert(
      fc.asyncProperty(
        failingStatusArb,
        jsonArb,
        fc.integer({ min: 0, max: 3_600 }),
        async (status, body, retryAfter) => {
          const response = new Response(JSON.stringify(body), {
            status,
            headers: { "Retry-After": String(retryAfter) },
          });
          const thrown = await client.handleResponse(response).then(
            () => null,
            (err: unknown) => err,
          );
          expect(thrown).toBeInstanceOf(DecisionEngineError);
          const error = thrown as DecisionEngineError;
          expect(error.statusCode).toBe(status);
          expect(error.errorCode).toBe(normalizedErrorCode(body, "unknown_error"));
          expect(error.message).toBe(normalizedErrorMessage(body));
          expect(error.responseBody).toEqual(JSON.parse(JSON.stringify(body)));
          const expectedClass =
            status === 401
              ? AuthenticationError
              : status === 404
                ? NotFoundError
                : status === 422
                  ? ValidationError
                  : status === 429
                    ? RateLimitError
                    : status >= 500
                      ? ServerError
                      : DecisionEngineError;
          expect(error.constructor).toBe(expectedClass);
          if (error instanceof RateLimitError) {
            expect(error.retryAfter).toBe(retryAfter);
          }
        },
      ),
      RUNS,
    );
    // 204/205 are the null-body success statuses the Response constructor forbids a body for.
    const successStatusArb = fc
      .integer({ min: 200, max: 299 })
      .filter((status) => status !== 204 && status !== 205);
    await fc.assert(
      fc.asyncProperty(successStatusArb, jsonArb, async (status, body) => {
        const response = new Response(JSON.stringify(body), { status });
        await expect(client.handleResponse(response)).resolves.toEqual(
          JSON.parse(JSON.stringify(body)),
        );
      }),
      RUNS,
    );
  });
});

// ---------------------------------------------------------------------------------------------
// Base URLs and hosts: the private-profile boundary
// ---------------------------------------------------------------------------------------------

describe("base URLs and hosts (privacy_profile, contract)", () => {
  it("normalizeBaseUrl trims whitespace and trailing slashes, changes nothing else, and is idempotent", () => {
    const urlArb = fc.webUrl({
      validSchemes: ["http", "https"],
      authoritySettings: { withPort: true },
      withQueryParameters: false,
      withFragments: false,
    });
    fc.assert(
      fc.property(urlArb, fc.nat({ max: 3 }), padArb, padArb, (url, slashes, lead, trail) => {
        const normalized = normalizeBaseUrl(`${lead}${url}${"/".repeat(slashes)}${trail}`, "test");
        expect(normalized).toBe(url.replace(/\/+$/, ""));
        expect(normalizeBaseUrl(normalized, "test")).toBe(normalized);
        expect(new URL(normalized).host).toBe(new URL(url).host);
      }),
      RUNS,
    );
  });

  it("normalizeBaseUrl is total: every string is normalized with a host or rejected with the absolute-URL message", () => {
    fc.assert(
      fc.property(fc.oneof(fc.string(), fc.string({ unit: "binary" }), fc.webUrl()), (raw) => {
        const thrown = captureError(() => normalizeBaseUrl(raw, "test"));
        if (thrown === null) {
          const normalized = normalizeBaseUrl(raw, "test");
          expect(normalized.endsWith("/")).toBe(false);
          expect(new URL(normalized).hostname.length).toBeGreaterThan(0);
          return;
        }
        expect(thrown).toBeInstanceOf(Error);
        expect((thrown as Error).message).toBe(
          "test baseUrl must be an absolute URL including scheme and host.",
        );
      }),
      RUNS,
    );
  });

  it("isAlgentaOwnedBaseUrl accepts every owned host and suffix in any case, and rejects other domains", () => {
    const labelArb = fc.stringMatching(/^[a-z0-9](?:[a-z0-9-]{0,15}[a-z0-9])?$/);
    const ownedHostArb = fc.oneof(
      fc.constantFrom(...ALGENTA_OWNED_HOSTS),
      fc
        .tuple(labelArb, fc.constantFrom(...ALGENTA_OWNED_SUFFIXES))
        .map(([label, suffix]) => `${label}${suffix}`),
    );
    fc.assert(
      fc.property(
        ownedHostArb,
        fc.constantFrom("http", "https"),
        fc.boolean(),
        fc.constantFrom("", "/", "/v1/decisions"),
        (host, scheme, upper, path) => {
          const url = `${scheme}://${upper ? host.toUpperCase() : host}${path}`;
          expect(isAlgentaOwnedBaseUrl(url)).toBe(true);
        },
      ),
      RUNS,
    );
    const ownedHosts = new Set<string>(ALGENTA_OWNED_HOSTS);
    const foreignDomainArb = fc.domain().filter((domain) => {
      const lower = domain.toLowerCase();
      return !ownedHosts.has(lower) && !ALGENTA_OWNED_SUFFIXES.some((suffix) => lower.endsWith(suffix));
    });
    fc.assert(
      fc.property(foreignDomainArb, (domain) => {
        expect(isAlgentaOwnedBaseUrl(`https://${domain}`)).toBe(false);
      }),
      RUNS,
    );
  });
});

// ---------------------------------------------------------------------------------------------
// Device headers: caller-provided device ids
// ---------------------------------------------------------------------------------------------

describe("device headers (client_device_headers)", () => {
  it("a provided X-Algenta-Device-Id is trimmed and echoed when 16-64 chars long, and rejected otherwise", () => {
    const coreArb = fc.string({ minLength: 16, maxLength: 64 }).filter((id) => id.trim() === id);
    fc.assert(
      fc.property(coreArb, padArb, padArb, fc.string({ minLength: 1, maxLength: 12 }), (core, lead, trail, version) => {
        const headers = resolveClientDeviceHeaders(version, {
          [DEVICE_ID_HEADER]: `${lead}${core}${trail}`,
        });
        expect(headers[DEVICE_ID_HEADER]).toBe(core);
        expect(headers[SDK_VERSION_HEADER]).toBe(version);
      }),
      RUNS,
    );
    const outOfRangeArb = fc
      .oneof(fc.string({ minLength: 1, maxLength: 15 }), fc.string({ minLength: 65, maxLength: 96 }))
      .filter((id) => {
        const length = id.trim().length;
        return length > 0 && (length < 16 || length > 64);
      });
    fc.assert(
      fc.property(outOfRangeArb, (deviceId) => {
        expect(() => resolveClientDeviceHeaders("0.0.0", { [DEVICE_ID_HEADER]: deviceId })).toThrow(
          /must be between 16 and 64 characters/,
        );
      }),
      RUNS,
    );
  });
});
