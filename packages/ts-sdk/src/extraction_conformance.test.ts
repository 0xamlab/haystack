/** Cross-language extraction conformance: TS side.
 *
 * Locks the shared aligned-column-extraction and typed-field-inference contract
 * against tests/conformance/extraction_vectors.json. The Python SDK asserts the
 * SAME literals (tests/test_extraction_conformance.py), so a pass in both
 * languages proves byte-identical behavior — pairwise/preserve alignment,
 * filter-before-alignment, limit truncation, input_hash, error codes/details,
 * and typed-field inference.
 *
 * Sources are seeded with a pinned schema_revision/dataset_id from the vectors
 * because connect()-time schema revision derivation is not yet cross-language
 * identical; input_hash parity is asserted over the pinned revision.
 */

import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { Runtime, RuntimeValidationError } from "./runtime.js";
import type { ColumnExtractOptions } from "./_runtime_class_methods_extract.js";
import type { LocalRecord } from "./_runtime_constants.js";

const vectorsPath = join(__dirname, "..", "..", "..", "tests", "conformance", "extraction_vectors.json");
const vectors = JSON.parse(readFileSync(vectorsPath, "utf-8"));

interface SourceSpec {
  name: string;
  dataset_id: string;
  schema_revision: string;
  records: LocalRecord[];
}

async function seededRuntime(sourceKey: string): Promise<{ runtime: Runtime; spec: SourceSpec }> {
  const spec = vectors.sources[sourceKey] as SourceSpec;
  const runtime = new Runtime();
  await runtime.connect(
    spec.records.map(record => ({ ...record })),
    { name: spec.name },
  );
  const source = runtime.localSources.get(spec.name)!;
  runtime.localSources.set(spec.name, {
    ...source,
    schemaRevision: spec.schema_revision,
    datasetId: spec.dataset_id,
  });
  return { runtime, spec };
}

function extractOptions(testCase: Record<string, unknown>): ColumnExtractOptions {
  const options: ColumnExtractOptions = {};
  if ("filter" in testCase) {
    options.filter = testCase.filter as Record<string, unknown>;
  }
  if ("limit" in testCase) {
    options.limit = testCase.limit as number;
  }
  if ("null_policy" in testCase) {
    options.nullPolicy = testCase.null_policy as "pairwise" | "preserve";
  }
  return options;
}

describe("extract columns conformance", () => {
  for (const testCase of vectors.extract) {
    it(testCase.name, async () => {
      const { runtime, spec } = await seededRuntime(testCase.source);
      const got = await runtime.extractColumns(spec.name, testCase.columns, extractOptions(testCase));
      expect(got.columns).toEqual(testCase.expected.columns);
      expect(got.row_count).toBe(testCase.expected.row_count);
      expect(got.input_hash).toBe(testCase.expected.input_hash);
      expect(got.source_name).toBe(spec.name);
      expect(got.schema_revision).toBe(spec.schema_revision);
      expect(got.alignment).toBe("rowwise");
    });
  }
});

describe("extract columns error conformance", () => {
  for (const testCase of vectors.extract_errors) {
    it(testCase.name, async () => {
      const { runtime } = await seededRuntime(testCase.source);
      let caught: unknown;
      try {
        await runtime.extractColumns(testCase.source_name, testCase.columns, extractOptions(testCase));
      } catch (error) {
        caught = error;
      }
      expect(caught).toBeInstanceOf(RuntimeValidationError);
      expect((caught as RuntimeValidationError).code).toBe(testCase.error_code);
      expect((caught as RuntimeValidationError).details).toEqual(testCase.details);
    });
  }
});

describe("typed fields conformance", () => {
  for (const testCase of vectors.typed_fields) {
    it(testCase.name, async () => {
      const runtime = new Runtime();
      const registration = await runtime.connect(
        (testCase.records as LocalRecord[]).map(record => ({ ...record })),
        { name: "typed_probe" },
      );
      expect(registration.typed_fields).toEqual(testCase.expected);
      const schema = registration.schema as Record<string, unknown>;
      const sourceSchema = registration.source_schema as Record<string, unknown>;
      expect(schema.typed_fields).toEqual(testCase.expected);
      expect(sourceSchema.typed_fields).toEqual(testCase.expected);
      // The existing fields array must stay untouched alongside typed_fields.
      expect(schema.fields).toEqual(
        (testCase.expected as Array<{ name: string }>).map(entry => entry.name),
      );
    });
  }
});

describe("extract columns error codes", () => {
  it("throws extract_requires_local_mode in api mode", async () => {
    const runtime = new Runtime({ mode: "api", apiKey: "de_test_extract" });
    let caught: unknown;
    try {
      await runtime.extractColumns("anything", ["revenue"]);
    } catch (error) {
      caught = error;
    }
    expect(caught).toBeInstanceOf(RuntimeValidationError);
    expect((caught as RuntimeValidationError).code).toBe("extract_requires_local_mode");
  });

  it("throws unknown_source without connections", async () => {
    const runtime = new Runtime();
    let caught: unknown;
    try {
      await runtime.extractColumns("anything", ["revenue"]);
    } catch (error) {
      caught = error;
    }
    expect(caught).toBeInstanceOf(RuntimeValidationError);
    expect((caught as RuntimeValidationError).code).toBe("unknown_source");
    expect((caught as RuntimeValidationError).details).toEqual({
      requested: "anything",
      available: [],
    });
  });
});
