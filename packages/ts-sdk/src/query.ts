// SPDX-License-Identifier: Apache-2.0
/**
 * Columnar queries on the local runtime — filter, group, sort, top-k, join, window,
 * in one call. Mirrors the Python SDK's `Query` builder
 * op-for-op, so a plan built here and a plan built in Python for the same
 * computation send the same wire JSON and hash the same `plan_hash`.
 *
 *   import { MojoRuntime, Query, col } from "@algenta/sdk";
 *
 *   const runtime = new MojoRuntime();
 *   const result = await new Query({ columns: ["region", "amount"], rows: [[1, 10.5], [2, 50], [1, 30]] })
 *     .filter(col("amount").gt(20))
 *     .groupBy("region", "amount", { agg: "sum" })
 *     .sort("sum_amount", { desc: true })
 *     .run(runtime);
 *   result.rows;       // [[2, 50], [1, 30]]
 *   result.planHash;   // identifies the computation, not the data
 *
 * Why a builder rather than SQL text: a plan is data — a list of ops and an
 * expression tree — so it can be hashed, compared, cached and shipped. `planHash`
 * is over the plan's VALUES, so whitespace and key order never change it and a
 * threshold does.
 *
 * Nulls are absences, not zeros: `null` in an input cell stays absent all the way
 * through and comes back as `null`. A predicate over an absent value is *unknown*,
 * and unknown does not pass a filter.
 *
 * A join reads a NAMED SIDE TABLE declared once per request, never inside an op —
 * `planHash` is over `ops`, so rows in an op would make the hash data-dependent.
 *
 * Unlike Python's `Query.run(runtime, routingModule=...)`, there is no shard
 * routing parameter here: the local runtime daemon this SDK talks to spawns one
 * worker process per socket, not shard-selected workers, so nothing to route.
 */
import type { MojoRuntime } from "./libraries.js";

// Opcodes must match the engine's query IR, and this file's own numbers must
// match the Python SDK's exactly — both compile the same IR.
const OP_LITERAL = 0;
const OP_ADD = 2;
const OP_SUB = 3;
const OP_MUL = 4;
const OP_DIV = 5;
const OP_NEG = 6;
const OP_LT = 100;
const OP_LE = 101;
const OP_GT = 102;
const OP_GE = 103;
const OP_EQ = 104;
const OP_NE = 105;
const OP_AND = 110;
const OP_OR = 111;
const OP_NOT = 112;
const OP_IS_NULL = 120;
const OP_IS_NOT_NULL = 121;
const OP_COALESCE = 122;
const OP_COL_REF = 130;
const OP_CASE_WHEN = 150;

const ACCEPTED_AGGREGATIONS = ["sum", "avg", "mean", "min", "max", "count", "var", "std"] as const;
type Aggregation = (typeof ACCEPTED_AGGREGATIONS)[number];

const ACCEPTED_JOIN_HOW = ["inner", "left", "semi", "anti"] as const;
const UNIMPLEMENTED_JOIN_HOW = ["right", "outer", "full", "cross"];
const ACCEPTED_JOIN_METHODS = ["hash", "merge", "direct_address"] as const;
const JOIN_HOW_WITHOUT_RIGHT_COLUMNS = ["semi", "anti"];
type JoinHow = (typeof ACCEPTED_JOIN_HOW)[number];
type JoinMethod = (typeof ACCEPTED_JOIN_METHODS)[number];

const ACCEPTED_WINDOW_FNS = [
  "row_number",
  "rank",
  "dense_rank",
  "lag",
  "lead",
  "cumulative",
  "framed",
  "partition_total",
] as const;
type WindowFn = (typeof ACCEPTED_WINDOW_FNS)[number];
// A window frame answers sum/avg/min/max/count. The engine also accepts var/std/
// median, but the frame kernels answer those with an all-null column and a success
// status, so they are rejected here rather than shipped.
const ACCEPTED_WINDOW_AGGREGATIONS = ["sum", "avg", "mean", "min", "max", "count"] as const;
type WindowAggregation = (typeof ACCEPTED_WINDOW_AGGREGATIONS)[number];
const WINDOW_FNS_TAKING_VALUE = ["lag", "lead", "cumulative", "framed", "partition_total"];
const WINDOW_FNS_TAKING_AGG = ["cumulative", "framed", "partition_total"];
const WINDOW_FNS_TAKING_OFFSET = ["lag", "lead"];
// Every fn except partition_total needs an order: a running total with no order is
// not a defined answer. partition_total is order-independent by definition.
const WINDOW_FNS_NEEDING_ORDER = [
  "row_number",
  "rank",
  "dense_rank",
  "lag",
  "lead",
  "cumulative",
  "framed",
];
// A tie is defined by the single order column, so several would report ties that
// are not ties.
const WINDOW_FNS_NEEDING_ONE_ORDER = ["rank", "dense_rank"];

// Python's builder bounds an integer to signed-64-bit (+/-2**63), because Python's
// arbitrary-precision `int` can hold an exact value out to there and beyond, and
// the engine's own arithmetic silently wraps past it. JS has no equivalent: every
// `number` is an IEEE-754 double, which stops representing every integer exactly
// at +/-(2**53 - 1) -- so a JS value anywhere near 2**63 has *already* lost the
// precision this check exists to protect, before this function ever sees it.
// `Number.isSafeInteger` is therefore the real boundary here, not a translation of
// Python's +/-2**63 -- and it is comfortably inside the wire's actual 64-bit range,
// so nothing safe-integer is ever wire-unsafe.

/** A query plan was rejected, or a builder call was invalid before it was ever sent.
 *
 * `code` is the engine's error code (`query_op_failed`, `invalid_arguments`,
 * `unknown_aggregation`, ...) — or a client-side `invalid_arguments` for a mistake
 * caught before the wire — and `opIndex` names which operator failed, when known. A
 * failed plan returns NO result: a partial answer would be indistinguishable from a
 * complete one. */
export class QueryError extends Error {
  readonly code: string;
  readonly opIndex: number | null;

  constructor(code: string, message: string, opIndex: number | null = null) {
    super(message);
    this.name = "QueryError";
    this.code = code;
    this.opIndex = opIndex;
  }
}

type ExprNode = {
  op: number;
  column?: string;
  value?: number;
  left?: number;
  right?: number;
  extra?: number;
};

function coerce(value: Expr | number | boolean): Expr {
  if (value instanceof Expr) return value;
  // Before the number check conceptually: in TS, `typeof true === "boolean"`, not
  // "number", so this branch is reached explicitly rather than falling through to
  // a silent 1/0 coercion the caller never asked for.
  if (typeof value === "boolean") return lit(value ? 1 : 0);
  if (typeof value === "number") return lit(value);
  throw new TypeError("cannot use this value in an expression; use a number, or col(name) for a column");
}

/** An expression tree, flattened on demand into the wire node array.
 *
 * Built with methods (`col("a").gt(20)`) so a predicate reads like the condition it
 * is. Immutable, so an expression can be reused across plans without one plan's
 * later mutation changing another's meaning. */
export class Expr {
  readonly op: number;
  readonly column?: string;
  readonly value?: number;
  readonly children: readonly Expr[];

  constructor(op: number, opts: { column?: string; value?: number; children?: readonly Expr[] } = {}) {
    this.op = op;
    this.column = opts.column;
    this.value = opts.value;
    this.children = opts.children ?? [];
  }

  // ── comparisons ───────────────────────────────────────────────────────────
  lt(other: Expr | number | boolean): Expr {
    return new Expr(OP_LT, { children: [this, coerce(other)] });
  }
  le(other: Expr | number | boolean): Expr {
    return new Expr(OP_LE, { children: [this, coerce(other)] });
  }
  gt(other: Expr | number | boolean): Expr {
    return new Expr(OP_GT, { children: [this, coerce(other)] });
  }
  ge(other: Expr | number | boolean): Expr {
    return new Expr(OP_GE, { children: [this, coerce(other)] });
  }
  eq(other: Expr | number | boolean): Expr {
    return new Expr(OP_EQ, { children: [this, coerce(other)] });
  }
  ne(other: Expr | number | boolean): Expr {
    return new Expr(OP_NE, { children: [this, coerce(other)] });
  }

  // ── logical, three-valued over nulls ──────────────────────────────────────
  and(other: Expr): Expr {
    return new Expr(OP_AND, { children: [this, other] });
  }
  or(other: Expr): Expr {
    return new Expr(OP_OR, { children: [this, other] });
  }
  not(): Expr {
    return new Expr(OP_NOT, { children: [this] });
  }

  // ── arithmetic ────────────────────────────────────────────────────────────
  add(other: Expr | number | boolean): Expr {
    return new Expr(OP_ADD, { children: [this, coerce(other)] });
  }
  sub(other: Expr | number | boolean): Expr {
    return new Expr(OP_SUB, { children: [this, coerce(other)] });
  }
  mul(other: Expr | number | boolean): Expr {
    return new Expr(OP_MUL, { children: [this, coerce(other)] });
  }
  div(other: Expr | number | boolean): Expr {
    return new Expr(OP_DIV, { children: [this, coerce(other)] });
  }
  neg(): Expr {
    return new Expr(OP_NEG, { children: [this] });
  }

  // ── null tests: the one place an absent input gives a known answer ────────
  isNull(): Expr {
    return new Expr(OP_IS_NULL, { children: [this] });
  }
  isNotNull(): Expr {
    return new Expr(OP_IS_NOT_NULL, { children: [this] });
  }
  coalesce(other: Expr | number | boolean): Expr {
    return new Expr(OP_COALESCE, { children: [this, coerce(other)] });
  }

  /** `CASE WHEN self THEN then ELSE elseValue END`, as one ternary node.
   *
   * `self` is the condition; an unknown (null) condition takes the `elseValue`
   * branch, matching SQL. For more than one `WHEN`, chain via `caseWhen`. */
  ifElse(then: Expr | number | boolean, elseValue: Expr | number | boolean): Expr {
    return new Expr(OP_CASE_WHEN, { children: [this, coerce(then), coerce(elseValue)] });
  }

  /** Flatten to `{nodes: [...], root: i}` with children before parents (postorder,
   * so a child's index is always lower than its parent's). */
  toPlan(): { nodes: ExprNode[]; root: number } {
    const nodes: ExprNode[] = [];
    const root = this.flatten(nodes);
    return { nodes, root };
  }

  /** @internal shared with `project`, which flattens several expressions into ONE
   * node array so two outputs reusing a subexpression evaluate it once. */
  flatten(nodes: ExprNode[]): number {
    const childIndices = this.children.map(child => child.flatten(nodes));
    const node: ExprNode = { op: this.op };
    if (this.column !== undefined) {
      node.column = this.column;
    } else if (this.children.length === 0) {
      node.value = this.value ?? 0;
    }
    if (childIndices.length >= 1) node.left = childIndices[0];
    if (childIndices.length >= 2) node.right = childIndices[1];
    if (childIndices.length >= 3) node.extra = childIndices[2];
    nodes.push(node);
    return nodes.length - 1;
  }
}

/** A reference to a column by NAME, resolved against the batch's header. By name
 * rather than index, so a plan does not silently target a different column when
 * the caller reorders its `columns` list. */
export function col(name: string): Expr {
  return new Expr(OP_COL_REF, { column: name });
}

/** A literal. Numbers keep their fraction: 20.5 is 20.5, not 20. */
export function lit(value: number): Expr {
  return new Expr(OP_LITERAL, { value });
}

/** `CASE WHEN c1 THEN v1 WHEN c2 THEN v2 ... ELSE elseValue END`.
 *
 * `branches` is a sequence of `[condition, value]` pairs, evaluated in order — the
 * first condition that is known-true wins. `elseValue` is required: this IR has no
 * literal that means "null". Builds a chain of ternary nodes, innermost first. */
export function caseWhen(
  branches: ReadonlyArray<readonly [Expr | number | boolean, Expr | number | boolean]>,
  elseValue: Expr | number | boolean,
): Expr {
  if (branches.length === 0) {
    throw new Error("caseWhen needs at least one [condition, value] pair");
  }
  let result = coerce(elseValue);
  for (let i = branches.length - 1; i >= 0; i--) {
    const [cond, then] = branches[i];
    result = coerce(cond).ifElse(then, result);
  }
  return result;
}

/** A query's output columns, its lineage and its plan hash. */
export class QueryResult {
  readonly columns: readonly string[];
  readonly rows: ReadonlyArray<ReadonlyArray<number | null>>;
  readonly lineage: ReadonlyArray<Record<string, unknown>>;
  readonly planHash: string;
  readonly ops: number;
  readonly latencyMs: number;
  /** How many result cells held a value that is not a real number, and so arrive as
   * `null`. A nonzero count means some `null` in `rows` is an arithmetic failure
   * (e.g. an overflowed sum), not a missing datum -- the two are indistinguishable
   * without this counter. */
  readonly nonFiniteCells: number;

  constructor(init: {
    columns: readonly string[];
    rows: ReadonlyArray<ReadonlyArray<number | null>>;
    lineage: ReadonlyArray<Record<string, unknown>>;
    planHash: string;
    ops: number;
    latencyMs: number;
    nonFiniteCells?: number;
  }) {
    this.columns = init.columns;
    this.rows = init.rows;
    this.lineage = init.lineage;
    this.planHash = init.planHash;
    this.ops = init.ops;
    this.latencyMs = init.latencyMs;
    this.nonFiniteCells = init.nonFiniteCells ?? 0;
  }

  get length(): number {
    return this.rows.length;
  }

  /** One output column by name. Throws if the plan did not produce it. */
  column(name: string): ReadonlyArray<number | null> {
    const index = this.columns.indexOf(name);
    if (index < 0) {
      throw new Error(`the result has no column '${name}'; it has [${this.columns.join(", ")}]`);
    }
    return this.rows.map(row => row[index]);
  }

  /** Rows as objects. Convenience only -- `rows` is the columnar-friendly form. */
  toDicts(): Array<Record<string, number | null>> {
    return this.rows.map(row => {
      const record: Record<string, number | null> = {};
      this.columns.forEach((name, i) => {
        record[name] = row[i];
      });
      return record;
    });
  }
}

function english(accepted: readonly string[]): string {
  if (accepted.length === 1) return accepted[0];
  return `${accepted.slice(0, -1).join(", ")} or ${accepted[accepted.length - 1]}`;
}

// Deliberately stricter than Python's `_wire_int`, which truncates a fractional
// float (`int(3.5) == 3`) rather than rejecting it. That silent truncation is not
// a contract worth carrying over: a caller who wrote 3.5 almost certainly did not
// mean 3, and rejecting is both easy and consistent for a value that is not a
// safe integer for either reason (fractional or out of range).
function wireInt(value: number, label: string, opIndex: number | null = null): number {
  if (!Number.isSafeInteger(value)) {
    throw new QueryError(
      "invalid_arguments",
      `${label} must be a safe integer (within +/-${Number.MAX_SAFE_INTEGER}); got ${value} ` +
        "(a JavaScript number stops representing every integer exactly beyond this range, " +
        "so a larger value is not reliably the number you wrote)",
      opIndex,
    );
  }
  return value;
}

/** A single name, a list of names, or nothing -- always out as a list. Names, not
 * indices, for the same reason every other op uses names: a reordered header must
 * not retarget the plan. */
function asNameList(
  value: string | readonly string[] | undefined,
  label: string,
  opIndex: number,
): string[] {
  if (value === undefined) return [];
  if (typeof value === "string") return [value];
  if (Array.isArray(value)) {
    for (const entry of value) {
      if (typeof entry !== "string" || entry.length === 0) {
        throw new QueryError("invalid_arguments", `window '${label}' takes column names; got ${JSON.stringify(entry)}`, opIndex);
      }
    }
    return [...value];
  }
  throw new QueryError("invalid_arguments", `window '${label}' must be a column name or a list of them`, opIndex);
}

/** Coerce cells to number or null, and check the width. Done here rather than in
 * the kernel so a bad cell is reported with its row and column while the caller
 * still has the original object to look at. */
function normalizeRows(rows: ReadonlyArray<ReadonlyArray<unknown>>, width: number): Array<Array<number | null>> {
  const out: Array<Array<number | null>> = [];
  rows.forEach((row, r) => {
    if (row.length > width) {
      throw new Error(`row ${r} has ${row.length} values but the header declares ${width} columns`);
    }
    const cells: Array<number | null> = [];
    row.forEach((cell, c) => {
      if (cell === null || cell === undefined) {
        cells.push(null);
      } else if (typeof cell === "boolean") {
        cells.push(cell ? 1 : 0);
      } else if (typeof cell === "number") {
        cells.push(cell);
      } else {
        throw new Error(`row ${r} column ${c} is ${typeof cell}; query columns are numeric or null`);
      }
    });
    out.push(cells);
  });
  return out;
}

interface TableEntry {
  name: string;
  columns: string[];
  rows?: Array<Array<number | null>>;
  dataset?: string;
}

export interface QueryTableSpec {
  name: string;
  columns: readonly string[];
  rows?: ReadonlyArray<ReadonlyArray<unknown>>;
  dataset?: string;
}

export interface QueryConfig {
  columns: readonly string[];
  rows?: ReadonlyArray<ReadonlyArray<unknown>>;
  dataset?: string;
  strict?: boolean;
  tables?: readonly QueryTableSpec[];
}

/** A columnar query plan. Each method appends an operator and returns `this`.
 *
 * Mutable and chained rather than immutable-and-copied: a plan is built once and
 * run once, and copying at every step would allocate an array per operator for no
 * benefit a caller can observe. */
export class Query {
  private readonly columns: string[];
  private readonly rows?: Array<Array<number | null>>;
  private readonly dataset?: string;
  private readonly strict: boolean;
  private readonly ops: Array<Record<string, unknown>> = [];
  // Side tables for `join`/`union`, alongside the plan rather than inside an op:
  // `planHash` is over `ops` only, so rows in an op would make the hash
  // data-dependent and two runs of the same computation over different data would
  // stop comparing.
  private readonly tables: TableEntry[] = [];

  constructor(config: QueryConfig) {
    if (!config.columns || config.columns.length === 0) {
      throw new Error("a query needs a non-empty columns list");
    }
    if (config.rows === undefined && config.dataset === undefined) {
      throw new Error("a query needs either rows or a dataset handle");
    }
    if (config.rows !== undefined && config.dataset !== undefined) {
      throw new Error(
        "pass rows OR dataset, not both -- sending both would leave which one is " +
          "authoritative up to the engine",
      );
    }
    this.columns = [...config.columns];
    this.dataset = config.dataset;
    this.rows = config.rows ? normalizeRows(config.rows, this.columns.length) : undefined;
    this.strict = config.strict ?? false;
    for (const table of config.tables ?? []) {
      this.withTable(table.name, table.columns, { rows: table.rows, dataset: table.dataset });
    }
  }

  // ── operators ─────────────────────────────────────────────────────────────

  /** Keep rows where `predicate` is present AND true. A row whose predicate is
   * *unknown* (any operand absent) does not pass -- not false, but not true either. */
  filter(predicate: Expr): Query {
    this.ops.push({ op: "filter", predicate: predicate.toPlan() });
    return this;
  }

  /** Compute one output column per entry. Expressions share one node array, so two
   * outputs reusing a subexpression evaluate it once. */
  project(expressions: Record<string, Expr>): Query {
    const names = Object.keys(expressions);
    if (names.length === 0) {
      throw new Error("project needs at least one expression");
    }
    const nodes: ExprNode[] = [];
    const roots: number[] = [];
    for (const name of names) {
      roots.push(expressions[name].flatten(nodes));
    }
    this.ops.push({ op: "project", expressions: { nodes, roots }, names });
    return this;
  }

  /** Keep these columns, in this order. No expression evaluation. */
  select(...names: string[]): Query {
    if (names.length === 0) {
      throw new Error("select needs at least one column name");
    }
    this.ops.push({ op: "select", columns: [...names] });
    return this;
  }

  /** Aggregate `value` grouped by `by`, in one pass. Rows whose GROUP KEY is absent
   * join no group and are counted separately -- folding them together would invent
   * a category. */
  groupBy(by: string | readonly string[], value: string, opts: { agg?: Aggregation } = {}): Query {
    const agg = opts.agg ?? "sum";
    if (!ACCEPTED_AGGREGATIONS.includes(agg)) {
      throw new Error(`unknown aggregation '${agg}'; accepted: ${ACCEPTED_AGGREGATIONS.join(", ")}`);
    }
    this.ops.push({ op: "aggregate", by, value, agg });
    return this;
  }

  /** Aggregate SEVERAL `[value, agg]` pairs grouped by `by`, in ONE pass -- the
   * engine runs every pair in the same grouped scan rather than one full rescan per
   * pair. Output columns are named `<agg>_<value>` per pair, in the order given. */
  groupByMany(by: string | readonly string[], aggs: ReadonlyArray<readonly [string, Aggregation]>): Query {
    if (aggs.length === 0) {
      throw new Error("groupByMany needs a non-empty list of [value, agg] pairs");
    }
    const resolved = aggs.map(([value, agg]) => {
      if (!ACCEPTED_AGGREGATIONS.includes(agg)) {
        throw new Error(`unknown aggregation '${agg}'; accepted: ${ACCEPTED_AGGREGATIONS.join(", ")}`);
      }
      return { value, agg };
    });
    this.ops.push({ op: "aggregate", by, aggs: resolved });
    return this;
  }

  /** Stable sort. Ties keep their input order. `nullsLast` applies in BOTH
   * directions: a null is not a large number, so `desc: true` must not answer with
   * the rows that have no value. */
  sort(
    by: string | readonly string[],
    opts: { desc?: boolean | readonly boolean[]; nullsLast?: boolean } = {},
  ): Query {
    const nullsLast = opts.nullsLast ?? true;
    const op: Record<string, unknown> = { op: "sort", by, nulls_last: nullsLast };
    if (Array.isArray(by)) {
      op.desc = Array.isArray(opts.desc) ? opts.desc : new Array(by.length).fill(Boolean(opts.desc));
    } else {
      if (Array.isArray(opts.desc)) {
        throw new Error("desc may only be a list when 'by' is a list");
      }
      op.desc = Boolean(opts.desc);
    }
    this.ops.push(op);
    return this;
  }

  /** The k best rows without sorting the rest -- O(n*k) and O(k) memory. Agrees
   * with `sort` on ordering, not merely on the set. */
  topK(by: string, k: number, opts: { desc?: boolean; nullsLast?: boolean } = {}): Query {
    const opIndex = this.ops.length;
    this.ops.push({
      op: "top_k",
      by,
      k: wireInt(k, "topK 'k'", opIndex),
      desc: opts.desc ?? true,
      nulls_last: opts.nullsLast ?? true,
    });
    return this;
  }

  /** First row of each distinct combination, in first-seen order. Two rows absent
   * in the same column are the SAME row here -- deliberately unlike `eq`, where
   * `null = null` is unknown. */
  distinct(...names: string[]): Query {
    this.ops.push({ op: "distinct", columns: [...names] });
    return this;
  }

  /** A row window. Clamps; a window past the end is empty. */
  limit(count: number, opts: { offset?: number } = {}): Query {
    const opIndex = this.ops.length;
    this.ops.push({
      op: "limit",
      offset: wireInt(opts.offset ?? 0, "limit 'offset'", opIndex),
      count: wireInt(count, "limit 'count'", opIndex),
    });
    return this;
  }

  // ── side tables, for join ──────────────────────────────────────────────────

  /** Declare a named table a later `join`/`union` can name. Sent once per request.
   *
   * A table lives beside the plan, not inside an op: `planHash` covers `ops`, so
   * rows in an op would make the hash data-dependent; a table joined twice would
   * otherwise be sent and parsed twice; and a 20-op plan over one dimension table
   * would ship it 20 times.
   *
   * `rows` inlines the data. `dataset` references a handle from an opened dataset
   * instead, making the per-request payload O(1) in rows -- a connection-scoped
   * optimization only; the op JSON is byte-identical either way.
   *
   * Engine bounds, enforced there and reported with the number it measured: at
   * most 8 side tables per request; at most 512 columns in a table's header; and
   * at most 32,000,000 cells (rows x columns) SUMMED over every side table in the
   * request, a budget a join's own output draws on as well. */
  withTable(
    name: string,
    columns: readonly string[],
    opts: { rows?: ReadonlyArray<ReadonlyArray<unknown>>; dataset?: string } = {},
  ): Query {
    if (!name) {
      throw new QueryError("invalid_arguments", "a table needs a non-empty name");
    }
    if (this.tables.some(table => table.name === name)) {
      throw new QueryError("invalid_arguments", `table '${name}' is declared twice`);
    }
    if (!columns || columns.length === 0) {
      throw new QueryError("invalid_arguments", `table '${name}' needs a non-empty columns list`);
    }
    const hasRows = opts.rows !== undefined;
    const hasDataset = opts.dataset !== undefined;
    if (hasRows === hasDataset) {
      throw new QueryError(
        "invalid_arguments",
        `table '${name}' needs exactly one of rows or dataset; sending both would ` +
          "leave which one is authoritative up to the engine, and neither leaves the " +
          "join with nothing to read",
      );
    }
    const entry: TableEntry = { name, columns: columns.map(String) };
    if (hasDataset) {
      if (!opts.dataset) {
        throw new QueryError("invalid_arguments", `table '${name}' has an empty dataset handle`);
      }
      entry.dataset = opts.dataset;
    } else {
      entry.rows = normalizeRows(opts.rows ?? [], entry.columns.length);
    }
    this.tables.push(entry);
    return this;
  }

  // ── join ──────────────────────────────────────────────────────────────────

  /** Join a named side table on ONE equality key.
   *
   * `how`: `inner`, `left`, `semi` or `anti`. `semi` keeps a left row that has a
   * partner and `anti` keeps one known to have none -- left columns only, one row
   * out per row in. They are SQL's `IN`/`NOT IN`, not `EXISTS`/`NOT EXISTS`: a left
   * row whose key is null is excluded from BOTH results. `right`, `outer`, `full`
   * and `cross` are rejected by name rather than quietly mapped to `left`.
   *
   * `method="merge"` walks two already-sorted inputs with no hash table -- only
   * usable when the table arrives sorted ascending with nulls last.
   *
   * `method="direct_address"` is a CALLER-DECLARED contract, not a hint: it
   * asserts the right key is an integer inside one bounded range, present at most
   * once per value (a bijection). When that holds, the engine skips the hash
   * table entirely and probes a flat array instead -- measured 1.88x faster end
   * to end on the one real shape this was built for (H2O join-track q5; see
   * `benchmarks/h2o_join/RESULTS.md`'s Update #6). When it does NOT hold, the
   * engine RAISES rather than silently falling back to `method="hash"`. */
  join(
    table: string,
    opts: {
      on?: string;
      leftOn?: string;
      rightOn?: string;
      how?: JoinHow;
      method?: JoinMethod;
      prefix?: string;
    } = {},
  ): Query {
    const opIndex = this.ops.length;
    if (!table) {
      throw new QueryError("invalid_arguments", "join requires 'table'", opIndex);
    }
    const how = opts.how ?? "inner";
    if ((UNIMPLEMENTED_JOIN_HOW as readonly string[]).includes(how)) {
      throw new QueryError(
        "invalid_arguments",
        `join 'how' must be ${english(ACCEPTED_JOIN_HOW)}; got '${how}' ` +
          "(right, outer, full and cross joins are not implemented)",
        opIndex,
      );
    }
    if (!(ACCEPTED_JOIN_HOW as readonly string[]).includes(how)) {
      throw new QueryError("invalid_arguments", `join 'how' must be ${english(ACCEPTED_JOIN_HOW)}; got '${how}'`, opIndex);
    }
    const method = opts.method ?? "hash";
    if (!(ACCEPTED_JOIN_METHODS as readonly string[]).includes(method)) {
      throw new QueryError(
        "invalid_arguments",
        `join 'method' must be ${english(ACCEPTED_JOIN_METHODS)}; got '${method}'`,
        opIndex,
      );
    }
    if (method !== "hash" && JOIN_HOW_WITHOUT_RIGHT_COLUMNS.includes(how)) {
      throw new QueryError("invalid_arguments", `join method '${method}' is not defined for how '${how}'`, opIndex);
    }
    let leftKey: string;
    let rightKey: string;
    if (opts.on !== undefined) {
      if (opts.leftOn !== undefined || opts.rightOn !== undefined) {
        throw new QueryError(
          "invalid_arguments",
          "join takes 'on', or both 'leftOn' and 'rightOn', not a mix -- which key " +
            "applies would be left to the engine",
          opIndex,
        );
      }
      leftKey = opts.on;
      rightKey = opts.on;
    } else {
      if (opts.leftOn === undefined || opts.rightOn === undefined) {
        throw new QueryError("invalid_arguments", "join requires 'on', or both 'leftOn' and 'rightOn'", opIndex);
      }
      leftKey = opts.leftOn;
      rightKey = opts.rightOn;
    }
    for (const [label, key] of [["leftOn", leftKey], ["rightOn", rightKey]] as const) {
      if (!key) {
        throw new QueryError(
          "invalid_arguments",
          `join '${label}' must be a single column name (a composite key would be a ` +
            "different algorithm and is not implemented)",
          opIndex,
        );
      }
    }
    if (opts.prefix !== undefined && JOIN_HOW_WITHOUT_RIGHT_COLUMNS.includes(how)) {
      throw new QueryError(
        "invalid_arguments",
        `join how '${how}' emits no right columns, so 'prefix' would have no effect; ` +
          "drop it or use how 'inner' or 'left'",
        opIndex,
      );
    }
    const op: Record<string, unknown> = {
      op: "join",
      table,
      left_on: leftKey,
      right_on: rightKey,
      how,
      method,
    };
    // Emitted only when asked for: the engine's default is "<table>.", and
    // spelling the default out here would make this builder's plan hash differ
    // from an equivalent plan built by another binding.
    if (opts.prefix !== undefined) {
      if (!opts.prefix) {
        throw new QueryError(
          "invalid_arguments",
          "an empty join prefix is not expressible -- it can only ask for a name " +
            "collision; omit prefix for the default '<table>.'",
          opIndex,
        );
      }
      op.prefix = opts.prefix;
    }
    this.ops.push(op);
    return this;
  }

  /** UNION ALL onto one or more named side tables (see `withTable`). Concatenates
   * rows: the running plan's rows first, then each named table's, in the given
   * order -- no deduplication. Columns are matched BY NAME, not by position. */
  union(...tables: string[]): Query {
    const opIndex = this.ops.length;
    if (tables.length === 0) {
      throw new QueryError("invalid_arguments", "union needs at least one table name", opIndex);
    }
    for (const table of tables) {
      if (!table) {
        throw new QueryError("invalid_arguments", "union table names must be non-empty strings", opIndex);
      }
    }
    this.ops.push({ op: "union", tables: [...tables] });
    return this;
  }

  // ── window ────────────────────────────────────────────────────────────────

  /** Append ONE window column, keeping row order exactly as it is.
   *
   * `name` is REQUIRED and becomes the wire key `"as"`: every default is either
   * ambiguous or collides with an existing column. Row order is NOT changed --
   * add a `sort` op afterwards for window order.
   *
   * Engine bounds: a window op accepts at most 20,000 input rows -- it orders the
   * RAW rows, and the cost of that grows quadratically, so a larger batch is
   * REFUSED. Reduce first with `filter`, `groupBy`, `topK` or `limit`. */
  window(
    fn: WindowFn,
    opts: {
      name: string;
      partitionBy?: string | readonly string[];
      orderBy?: string | readonly string[];
      desc?: boolean | readonly boolean[];
      value?: string;
      agg?: WindowAggregation;
      offset?: number;
      preceding?: number;
      nullsLast?: boolean;
    },
  ): Query {
    const opIndex = this.ops.length;
    if (!(ACCEPTED_WINDOW_FNS as readonly string[]).includes(fn)) {
      throw new QueryError("invalid_arguments", `window 'fn' must be ${english(ACCEPTED_WINDOW_FNS)}; got '${fn}'`, opIndex);
    }
    if (!opts.name) {
      throw new QueryError("invalid_arguments", "window requires 'name' (the output column name)", opIndex);
    }

    const partitions = asNameList(opts.partitionBy, "partitionBy", opIndex);
    const orders = asNameList(opts.orderBy, "orderBy", opIndex);

    if (WINDOW_FNS_NEEDING_ORDER.includes(fn) && orders.length === 0) {
      throw new QueryError("invalid_arguments", `window fn '${fn}' requires a non-empty 'orderBy'`, opIndex);
    }
    if (WINDOW_FNS_NEEDING_ONE_ORDER.includes(fn) && orders.length !== 1) {
      throw new QueryError(
        "invalid_arguments",
        `window fn '${fn}' requires exactly one 'orderBy' column; got ${orders.length}`,
        opIndex,
      );
    }

    let descList: boolean[] | undefined;
    if (opts.desc !== undefined) {
      descList = Array.isArray(opts.desc) ? [...opts.desc] : new Array(orders.length).fill(opts.desc);
      // One boolean per order column. A short list silently leaves the trailing
      // keys ascending, which is a different ordering and hence different ranks.
      if (descList.length !== orders.length) {
        throw new QueryError(
          "invalid_arguments",
          `window 'desc' must be an array of one boolean per 'orderBy' column ` +
            `(${orders.length} expected, ${descList.length} given)`,
          opIndex,
        );
      }
    }

    if (WINDOW_FNS_TAKING_VALUE.includes(fn)) {
      if (!opts.value) {
        throw new QueryError("invalid_arguments", `window fn '${fn}' requires 'value'`, opIndex);
      }
    } else if (opts.value !== undefined) {
      throw new QueryError("invalid_arguments", `window fn '${fn}' takes no 'value'`, opIndex);
    }

    if (WINDOW_FNS_TAKING_AGG.includes(fn)) {
      if (opts.agg === undefined) {
        throw new QueryError("invalid_arguments", `window fn '${fn}' requires 'agg'`, opIndex);
      }
      if (!(ACCEPTED_WINDOW_AGGREGATIONS as readonly string[]).includes(opts.agg)) {
        throw new QueryError(
          "invalid_arguments",
          `window 'agg' must be sum, avg, min, max or count; got '${opts.agg}' (var, ` +
            "std and median are not defined over a window frame here)",
          opIndex,
        );
      }
    } else if (opts.agg !== undefined) {
      throw new QueryError("invalid_arguments", `window fn '${fn}' takes no 'agg'`, opIndex);
    }

    let offsetValue = 1;
    if (WINDOW_FNS_TAKING_OFFSET.includes(fn)) {
      offsetValue = opts.offset === undefined ? 1 : wireInt(opts.offset, `window fn '${fn}' 'offset'`, opIndex);
      if (offsetValue < 1) {
        // A signed offset is deliberately not the wire API: "lag" with -1 would
        // silently be a lead.
        throw new QueryError("invalid_arguments", `window fn '${fn}' requires 'offset' >= 1`, opIndex);
      }
    } else if (opts.offset !== undefined) {
      throw new QueryError("invalid_arguments", `window fn '${fn}' takes no 'offset'`, opIndex);
    }

    let precedingValue = 0;
    if (fn === "framed") {
      if (opts.preceding === undefined) {
        throw new QueryError(
          "invalid_arguments",
          "window fn 'framed' requires 'preceding' >= 0; use fn 'cumulative' for an unbounded frame",
          opIndex,
        );
      }
      precedingValue = wireInt(opts.preceding, "window fn 'framed' 'preceding'", opIndex);
      if (precedingValue < 0) {
        // -1 is FRAME_UNBOUNDED inside the kernel and never appears on the wire,
        // so a stray -1 cannot turn a rolling frame into a cumulative one.
        throw new QueryError(
          "invalid_arguments",
          "window fn 'framed' requires 'preceding' >= 0; use fn 'cumulative' for an unbounded frame",
          opIndex,
        );
      }
    } else if (opts.preceding !== undefined) {
      throw new QueryError(
        "invalid_arguments",
        `window fn '${fn}' takes no 'preceding'; use fn 'framed' for a rolling frame`,
        opIndex,
      );
    }

    const op: Record<string, unknown> = {
      op: "window",
      fn,
      as: opts.name,
      nulls_last: opts.nullsLast ?? true,
    };
    if (partitions.length > 0) op.partition_by = partitions;
    if (orders.length > 0) op.order_by = orders;
    if (descList !== undefined) op.desc = descList;
    if (opts.value !== undefined) op.value = opts.value;
    if (opts.agg !== undefined) op.agg = opts.agg;
    if (WINDOW_FNS_TAKING_OFFSET.includes(fn)) op.offset = offsetValue;
    if (fn === "framed") op.preceding = precedingValue;
    this.ops.push(op);
    return this;
  }

  // ── window sugar: the same op, spelled as the function it computes ─────────

  /** 1-based position within the partition. Never null, never tied. */
  rowNumber(opts: {
    name: string;
    orderBy: string | readonly string[];
    partitionBy?: string | readonly string[];
    desc?: boolean | readonly boolean[];
    nullsLast?: boolean;
  }): Query {
    return this.window("row_number", opts);
  }

  /** Competition rank: 10,20,20,30 -> 1,2,2,4. Gaps after a tie. */
  rank(opts: {
    name: string;
    orderBy: string;
    partitionBy?: string | readonly string[];
    desc?: boolean;
    nullsLast?: boolean;
  }): Query {
    return this.window("rank", opts);
  }

  /** Dense rank: 10,20,20,30 -> 1,2,2,3. No gaps. */
  denseRank(opts: {
    name: string;
    orderBy: string;
    partitionBy?: string | readonly string[];
    desc?: boolean;
    nullsLast?: boolean;
  }): Query {
    return this.window("dense_rank", opts);
  }

  /** The value `offset` rows earlier in the partition; absent at the edge. */
  lag(
    value: string,
    opts: {
      name: string;
      orderBy: string | readonly string[];
      partitionBy?: string | readonly string[];
      offset?: number;
      desc?: boolean | readonly boolean[];
      nullsLast?: boolean;
    },
  ): Query {
    return this.window("lag", { ...opts, value, offset: opts.offset ?? 1 });
  }

  /** The value `offset` rows later in the partition; absent at the edge. */
  lead(
    value: string,
    opts: {
      name: string;
      orderBy: string | readonly string[];
      partitionBy?: string | readonly string[];
      offset?: number;
      desc?: boolean | readonly boolean[];
      nullsLast?: boolean;
    },
  ): Query {
    return this.window("lead", { ...opts, value, offset: opts.offset ?? 1 });
  }

  /** A running aggregate over the partition so far -- the unbounded frame. */
  running(
    value: string,
    opts: {
      name: string;
      orderBy: string | readonly string[];
      partitionBy?: string | readonly string[];
      agg?: WindowAggregation;
      desc?: boolean | readonly boolean[];
      nullsLast?: boolean;
    },
  ): Query {
    return this.window("cumulative", { ...opts, value, agg: opts.agg ?? "sum" });
  }

  /** A trailing frame of `preceding + 1` rows, clamped at the partition start. */
  rolling(
    value: string,
    opts: {
      name: string;
      orderBy: string | readonly string[];
      preceding: number;
      partitionBy?: string | readonly string[];
      agg?: WindowAggregation;
      desc?: boolean | readonly boolean[];
      nullsLast?: boolean;
    },
  ): Query {
    return this.window("framed", { ...opts, value, agg: opts.agg ?? "sum" });
  }

  /** The partition's aggregate on every row of it -- a share-of-total with no
   * join. Order-independent, so no `orderBy`: it would change nothing. */
  partitionTotal(
    value: string,
    opts: {
      name: string;
      partitionBy?: string | readonly string[];
      agg?: WindowAggregation;
      nullsLast?: boolean;
    },
  ): Query {
    return this.window("partition_total", { ...opts, value, agg: opts.agg ?? "sum" });
  }

  // ── execution ─────────────────────────────────────────────────────────────

  /** The wire frame this plan will send. Useful for hashing or inspection. */
  toRequest(): Record<string, unknown> {
    const declared = this.tables.map(table => table.name);
    this.ops.forEach((op, index) => {
      if (op.op === "join") {
        if (!declared.includes(op.table as string)) {
          throw new QueryError(
            "invalid_arguments",
            `join references table '${String(op.table)}', which the plan does not ` +
              `supply (available: ${declared.join(", ") || "none"})`,
            index,
          );
        }
      } else if (op.op === "union") {
        for (const name of (op.tables as string[]) ?? []) {
          if (!declared.includes(name)) {
            throw new QueryError(
              "invalid_arguments",
              `union references table '${name}', which the plan does not supply ` +
                `(available: ${declared.join(", ") || "none"})`,
              index,
            );
          }
        }
      }
    });
    const request: Record<string, unknown> = {
      type: "query_execute",
      columns: [...this.columns],
      ops: [...this.ops],
      strict: this.strict,
    };
    if (this.dataset !== undefined) {
      request.dataset = this.dataset;
    } else {
      request.rows = this.rows ?? [];
    }
    // Only when non-empty, so a plan without side tables sends the byte-identical
    // request it sent before joins existed, and no plan hash moves.
    if (this.tables.length > 0) {
      request.tables = this.tables.map(table => ({ ...table }));
    }
    return request;
  }

  /** Execute the whole plan in one dispatch on this device. */
  async run(runtime: MojoRuntime): Promise<QueryResult> {
    return runtime.query(this);
  }
}
