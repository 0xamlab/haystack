/** Auto-split sub-module of runtime.ts — aligned column extraction primitive
 * for the Runtime class (local mode only in v1).
 *
 * This module augments the {@link Runtime} class via TypeScript declaration
 * merging and prototype assignment. Importing this file (for its side
 * effects) is required so the prototype assignments execute and the
 * augmented methods are available on `Runtime` instances.
 */

import type { ColumnExtractResult } from "./types.js";
import { Runtime } from "./_runtime_class.js";
import { RuntimeValidationError } from "./_runtime_errors.js";
import { stableHash } from "./_runtime_helpers_a.js";
import {
  applyLocalFilterConditions,
  numericValue,
  resolveLocalFilterConditions,
} from "./_runtime_helpers_b.js";

export interface ColumnExtractOptions {
  filter?: Record<string, unknown>;
  limit?: number;
  nullPolicy?: "pairwise" | "preserve";
}

const EXTRACT_NULL_POLICIES = ["pairwise", "preserve"] as const;

declare module "./_runtime_class.js" {
  interface Runtime {
    extractColumns(
      sourceName: string,
      columns: string[],
      options?: ColumnExtractOptions,
    ): Promise<ColumnExtractResult>;
  }
}

/** Extract rowwise-aligned numeric columns from a connected local source.
 *
 * Semantics mirror the Python SDK's Runtime.extract_columns exactly
 * (conformance-tested): filters run through the shared local filter helpers,
 * cells are admitted via numericValue, nullPolicy 'pairwise' keeps only
 * rowwise-complete rows while 'preserve' keeps nulls, and limit truncates
 * AFTER filtering/alignment. */
Runtime.prototype.extractColumns = async function (
  this: Runtime,
  sourceName: string,
  columns: string[],
  options: ColumnExtractOptions = {},
): Promise<ColumnExtractResult> {
  if (this.usesApiTransport()) {
    throw new RuntimeValidationError(
      "extract_requires_local_mode",
      "Runtime.extractColumns() is local-mode only in v1. Construct Runtime({ mode: 'local' }).",
    );
  }
  const source = this.selectLocalSource({ source_name: sourceName });
  const nullPolicy = options.nullPolicy ?? "pairwise";
  if (!EXTRACT_NULL_POLICIES.includes(nullPolicy)) {
    throw new RuntimeValidationError(
      "invalid_null_policy",
      `Unknown null_policy '${nullPolicy}'. Supported: pairwise, preserve.`,
      { null_policy: nullPolicy, supported: [...EXTRACT_NULL_POLICIES] },
    );
  }
  for (const column of columns) {
    if (!source.fields.includes(column)) {
      throw new RuntimeValidationError(
        "unknown_column",
        `Column '${column}' is not present on source '${source.name}'.`,
        { column, available: [...source.fields].sort() },
      );
    }
  }
  await this.ensureLocalExecutionEntitlement();

  const conditions = resolveLocalFilterConditions(source, options.filter ?? {});
  const { records: filteredRecords } = applyLocalFilterConditions(source.records, conditions);

  const alignedRows: Array<Array<number | null>> = [];
  for (const record of filteredRecords) {
    const cells = columns.map(column => numericValue(record[column]));
    if (nullPolicy === "pairwise" && cells.some(cell => cell === null)) {
      continue;
    }
    alignedRows.push(cells);
  }
  // Truncate AFTER filtering/alignment; negative limits clamp to zero rows.
  const limitedRows =
    options.limit == null
      ? alignedRows
      : alignedRows.slice(0, Math.max(0, Math.trunc(options.limit)));

  const extracted: Record<string, Array<number | null>> = {};
  columns.forEach((column, index) => {
    extracted[column] = limitedRows.map(cells => cells[index]);
  });

  // Hash payload is shared verbatim with the Python SDK; null-stripping is
  // intentionally NOT applied so `limit: null` hashes explicitly.
  const inputHash = stableHash({
    source_name: source.name,
    schema_revision: source.schemaRevision,
    columns: [...columns].sort(),
    filter: options.filter ?? {},
    limit: options.limit ?? null,
    null_policy: nullPolicy,
  });

  return {
    columns: extracted,
    row_count: limitedRows.length,
    source_name: source.name,
    schema_revision: source.schemaRevision,
    alignment: "rowwise",
    input_hash: inputHash,
  };
};
