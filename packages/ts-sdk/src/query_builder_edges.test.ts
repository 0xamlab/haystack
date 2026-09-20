// SPDX-License-Identifier: Apache-2.0
// Edge cases of the Query builder that query.test.ts leaves open: every Expr
// operator's opcode, literal coercion, the wire shape of each operator's happy
// path, and the guard rails on withTable/join/union/window.
import { describe, expect, it, vi } from "vitest";

import type { MojoRuntime } from "./libraries.js";
import { Expr, Query, QueryError, QueryResult, col, lit } from "./query.js";

type Op = Record<string, unknown>;

// Opcodes are the engine's query IR and match the Python SDK's numbers exactly,
// so they are asserted as literals here rather than imported.
const OP_LITERAL = 0;
const OP_COL_REF = 130;

function ops(query: Query): Op[] {
  return query.toRequest().ops as Op[];
}

function base(): Query {
  return new Query({ columns: ["region", "amount"], rows: [[1, 10]] });
}

function queryError(fn: () => unknown): QueryError {
  try {
    fn();
  } catch (error) {
    if (error instanceof QueryError) {
      return error;
    }
    throw error;
  }
  throw new Error("expected a QueryError to be thrown");
}

describe("Expr operators", () => {
  it.each([
    ["lt", 100],
    ["le", 101],
    ["gt", 102],
    ["ge", 103],
    ["eq", 104],
    ["ne", 105],
    ["add", 2],
    ["sub", 3],
    ["mul", 4],
    ["div", 5],
    ["coalesce", 122],
  ] as const)("%s emits opcode %i over [column, literal] in postorder", (method, opcode) => {
    const plan = col("a")[method](2.5).toPlan();

    expect(plan).toEqual({
      nodes: [
        { op: OP_COL_REF, column: "a" },
        { op: OP_LITERAL, value: 2.5 },
        { op: opcode, left: 0, right: 1 },
      ],
      root: 2,
    });
  });

  it.each([
    ["not", 112],
    ["neg", 6],
    ["isNull", 120],
    ["isNotNull", 121],
  ] as const)("%s emits opcode %i with a single left child", (method, opcode) => {
    const plan = col("a")[method]().toPlan();

    expect(plan).toEqual({
      nodes: [
        { op: OP_COL_REF, column: "a" },
        { op: opcode, left: 0 },
      ],
      root: 1,
    });
  });

  it.each([
    ["and", 110],
    ["or", 111],
  ] as const)("%s combines two predicates under opcode %i", (method, opcode) => {
    const plan = col("a").gt(1)[method](col("b").lt(2)).toPlan();

    expect(plan.nodes).toHaveLength(7);
    expect(plan.nodes[plan.root]).toEqual({ op: opcode, left: 2, right: 5 });
  });

  it("ifElse emits a ternary node whose third child is `extra`", () => {
    const plan = col("flag").ifElse(1, 2).toPlan();

    expect(plan.nodes[plan.root]).toEqual({ op: 150, left: 0, right: 1, extra: 2 });
  });

  it.each([
    [true, 1],
    [false, 0],
    [3, 3],
  ])("coerces the literal operand %s to the numeric literal %i", (operand, value) => {
    const plan = col("a").eq(operand).toPlan();

    expect(plan.nodes[1]).toEqual({ op: OP_LITERAL, value });
  });

  it("rejects an operand that is neither an Expr, a number nor a boolean", () => {
    expect(() => col("a").eq("x" as never)).toThrowError(TypeError);
    expect(() => col("a").eq("x" as never)).toThrowError(/use a number, or col\(name\)/);
  });

  it("flattens a leaf with no value as the literal 0", () => {
    expect(new Expr(OP_LITERAL).toPlan()).toEqual({
      nodes: [{ op: OP_LITERAL, value: 0 }],
      root: 0,
    });
    expect(lit(4.5).toPlan().nodes).toEqual([{ op: OP_LITERAL, value: 4.5 }]);
  });
});

describe("QueryResult", () => {
  it("reports its row count as length and defaults nonFiniteCells to 0", () => {
    const init = { columns: ["a"], lineage: [], planHash: "h", ops: 1, latencyMs: 2 };

    expect(new QueryResult({ ...init, rows: [[1], [2], [null]] }).length).toBe(3);
    expect(new QueryResult({ ...init, rows: [] }).nonFiniteCells).toBe(0);
    expect(new QueryResult({ ...init, rows: [], nonFiniteCells: 4 }).nonFiniteCells).toBe(4);
  });
});

describe("Query construction and request framing", () => {
  it("declares side tables passed through the config", () => {
    const request = new Query({
      columns: ["a"],
      rows: [[1]],
      tables: [
        { name: "inline", columns: ["id"], rows: [[true], [null]] },
        { name: "handle", columns: ["id"], dataset: "ds_side" },
      ],
    }).toRequest();

    expect(request.tables).toEqual([
      { name: "inline", columns: ["id"], rows: [[1], [null]] },
      { name: "handle", columns: ["id"], dataset: "ds_side" },
    ]);
  });

  it("rejects a non-numeric cell, naming its row and column", () => {
    expect(() => new Query({ columns: ["a", "b"], rows: [[1, "x"]] })).toThrowError(
      "row 0 column 1 is string; query columns are numeric or null",
    );
  });

  it("frames a dataset-backed plan with the handle and no rows", () => {
    const request = new Query({ columns: ["a"], dataset: "ds_main", strict: true }).toRequest();

    expect(request).toEqual({
      type: "query_execute",
      columns: ["a"],
      ops: [],
      strict: true,
      dataset: "ds_main",
    });
    expect(request).not.toHaveProperty("rows");
    expect(request).not.toHaveProperty("tables");
  });

  it("frames a rows-backed plan without a dataset key", () => {
    const request = new Query({ columns: ["a"], rows: [[1]] }).toRequest();

    expect(request.rows).toEqual([[1]]);
    expect(request.strict).toBe(false);
    expect(request).not.toHaveProperty("dataset");
  });

  it("run() hands itself to the runtime's query()", async () => {
    const result = new QueryResult({
      columns: ["a"],
      rows: [[1]],
      lineage: [],
      planHash: "h",
      ops: 1,
      latencyMs: 0,
    });
    const runtime = { query: vi.fn(async () => result) };
    const query = new Query({ columns: ["a"], rows: [[1]] }).select("a");

    await expect(query.run(runtime as unknown as MojoRuntime)).resolves.toBe(result);
    expect(runtime.query).toHaveBeenCalledWith(query);
  });
});

describe("project", () => {
  it("flattens every expression into one node array with one root per output", () => {
    const amount = col("amount");
    const [op] = ops(base().project({ doubled: amount.mul(2), bumped: amount.add(1) }));

    expect(op).toEqual({
      op: "project",
      names: ["doubled", "bumped"],
      expressions: {
        nodes: [
          { op: OP_COL_REF, column: "amount" },
          { op: OP_LITERAL, value: 2 },
          { op: 4, left: 0, right: 1 },
          { op: OP_COL_REF, column: "amount" },
          { op: OP_LITERAL, value: 1 },
          { op: 2, left: 3, right: 4 },
        ],
        roots: [2, 5],
      },
    });
  });
});

describe("groupBy and groupByMany", () => {
  it("groupBy defaults the aggregation to sum and keeps an explicit one", () => {
    expect(ops(base().groupBy("region", "amount"))).toEqual([
      { op: "aggregate", by: "region", value: "amount", agg: "sum" },
    ]);
    expect(ops(base().groupBy(["region"], "amount", { agg: "max" }))[0].agg).toBe("max");
  });

  it("groupByMany emits one aggs entry per pair, in order", () => {
    expect(
      ops(
        base().groupByMany(["region"], [
          ["amount", "sum"],
          ["amount", "count"],
        ]),
      ),
    ).toEqual([
      {
        op: "aggregate",
        by: ["region"],
        aggs: [
          { value: "amount", agg: "sum" },
          { value: "amount", agg: "count" },
        ],
      },
    ]);
  });

  it("groupByMany rejects an empty pair list and an unknown aggregation", () => {
    expect(() => base().groupByMany("region", [])).toThrowError(
      "groupByMany needs a non-empty list of [value, agg] pairs",
    );
    expect(() => base().groupByMany("region", [["amount", "median" as never]])).toThrowError(
      /unknown aggregation 'median'/,
    );
  });
});

describe("sort, topK, distinct and limit", () => {
  it("sort with a scalar key emits a scalar desc and nulls_last", () => {
    expect(ops(base().sort("amount"))).toEqual([
      { op: "sort", by: "amount", nulls_last: true, desc: false },
    ]);
    expect(ops(base().sort("amount", { desc: true, nullsLast: false }))).toEqual([
      { op: "sort", by: "amount", nulls_last: false, desc: true },
    ]);
  });

  it("sort with a key list expands a scalar desc and passes a list through", () => {
    expect(ops(base().sort(["region", "amount"], { desc: true }))[0].desc).toEqual([true, true]);
    expect(ops(base().sort(["region", "amount"]))[0].desc).toEqual([false, false]);
    expect(ops(base().sort(["region", "amount"], { desc: [true, false] }))[0].desc).toEqual([
      true,
      false,
    ]);
  });

  it("topK defaults to descending with nulls last", () => {
    expect(ops(base().topK("amount", 3))).toEqual([
      { op: "top_k", by: "amount", k: 3, desc: true, nulls_last: true },
    ]);
    expect(ops(base().topK("amount", 3, { desc: false, nullsLast: false }))[0]).toMatchObject({
      desc: false,
      nulls_last: false,
    });
  });

  it("distinct lists the columns and limit defaults its offset to 0", () => {
    expect(ops(base().distinct("region", "amount"))).toEqual([
      { op: "distinct", columns: ["region", "amount"] },
    ]);
    expect(ops(base().limit(5))).toEqual([{ op: "limit", offset: 0, count: 5 }]);
    expect(ops(base().limit(5, { offset: 10 }))).toEqual([{ op: "limit", offset: 10, count: 5 }]);
  });
});

describe("withTable", () => {
  it.each([
    ["an empty name", () => base().withTable("", ["id"], { rows: [] }), "a table needs a non-empty name"],
    [
      "an empty column list",
      () => base().withTable("t", [], { rows: [] }),
      "table 't' needs a non-empty columns list",
    ],
    [
      "an empty dataset handle",
      () => base().withTable("t", ["id"], { dataset: "" }),
      "table 't' has an empty dataset handle",
    ],
  ])("rejects %s as invalid_arguments", (_label, build, message) => {
    const error = queryError(build);

    expect(error.code).toBe("invalid_arguments");
    expect(error.message).toBe(message);
    expect(error.opIndex).toBeNull();
  });

  it("records a dataset-backed table with no rows key", () => {
    const request = base().withTable("dim", ["id", "tier"], { dataset: "ds_dim" }).toRequest();

    expect(request.tables).toEqual([{ name: "dim", columns: ["id", "tier"], dataset: "ds_dim" }]);
  });
});

describe("join", () => {
  const withSide = () => base().withTable("c", ["id"], { rows: [[1]] });

  it("requires a table name and reports the op index of the failing join", () => {
    const error = queryError(() => withSide().select("region").join(""));

    expect(error.code).toBe("invalid_arguments");
    expect(error.message).toBe("join requires 'table'");
    expect(error.opIndex).toBe(1);
  });

  it("rejects an unknown how that is not one of the named unimplemented joins", () => {
    expect(() => withSide().join("c", { on: "id", how: "sideways" as never })).toThrowError(
      "join 'how' must be inner, left, semi or anti; got 'sideways'",
    );
  });

  it("requires both leftOn and rightOn when on is omitted", () => {
    expect(() => withSide().join("c", { leftOn: "region" })).toThrowError(
      "join requires 'on', or both 'leftOn' and 'rightOn'",
    );
    expect(() => withSide().join("c", { rightOn: "id" })).toThrowError(
      "join requires 'on', or both 'leftOn' and 'rightOn'",
    );
  });

  it.each([
    ["leftOn", { leftOn: "", rightOn: "id" }],
    ["rightOn", { leftOn: "region", rightOn: "" }],
    ["leftOn", { on: "" }],
  ])("rejects an empty %s key", (label, opts) => {
    expect(() => withSide().join("c", opts)).toThrowError(
      `join '${label}' must be a single column name`,
    );
  });

  it("names 'none' as the available tables when a join references one and none exist", () => {
    const query = base().join("orders", { on: "region" });

    expect(() => query.toRequest()).toThrowError(
      /join references table 'orders', which the plan does not supply \(available: none\)/,
    );
  });

  it.each(["inner", "left"] as const)("emits an explicit prefix for a %s join", how => {
    const [op] = ops(withSide().join("c", { leftOn: "region", rightOn: "id", how, prefix: "c_" }));

    expect(op).toEqual({
      op: "join",
      table: "c",
      left_on: "region",
      right_on: "id",
      how,
      method: "hash",
      prefix: "c_",
    });
  });
});

describe("union", () => {
  it("emits the table list in the given order", () => {
    const query = base()
      .withTable("t1", ["region", "amount"], { rows: [[2, 20]] })
      .withTable("t2", ["region", "amount"], { dataset: "ds_t2" })
      .union("t2", "t1");

    expect(ops(query)).toEqual([{ op: "union", tables: ["t2", "t1"] }]);
  });

  it("rejects an empty table name", () => {
    const error = queryError(() => base().select("region").union("t1", ""));

    expect(error.message).toBe("union table names must be non-empty strings");
    expect(error.opIndex).toBe(1);
  });
});

describe("window guard rails", () => {
  it("rejects an unknown function, listing every accepted one", () => {
    expect(() => base().window("ntile" as never, { name: "n", orderBy: "amount" })).toThrowError(
      "window 'fn' must be row_number, rank, dense_rank, lag, lead, cumulative, framed or " +
        "partition_total; got 'ntile'",
    );
  });

  it.each([
    [
      "a value on a function that takes none",
      { fn: "row_number", opts: { name: "n", orderBy: "amount", value: "amount" } },
      "window fn 'row_number' takes no 'value'",
    ],
    [
      "a missing value on lag",
      { fn: "lag", opts: { name: "n", orderBy: "amount" } },
      "window fn 'lag' requires 'value'",
    ],
    [
      "a missing agg on cumulative",
      { fn: "cumulative", opts: { name: "n", orderBy: "amount", value: "amount" } },
      "window fn 'cumulative' requires 'agg'",
    ],
    [
      "an aggregation the frame kernels do not answer",
      { fn: "cumulative", opts: { name: "n", orderBy: "amount", value: "amount", agg: "median" } },
      /window 'agg' must be sum, avg, min, max or count; got 'median'/,
    ],
    [
      "an agg on a function that takes none",
      { fn: "rank", opts: { name: "n", orderBy: "amount", agg: "sum" } },
      "window fn 'rank' takes no 'agg'",
    ],
    [
      "an offset on a function that takes none",
      { fn: "rank", opts: { name: "n", orderBy: "amount", offset: 2 } },
      "window fn 'rank' takes no 'offset'",
    ],
    [
      "a negative preceding on framed",
      { fn: "framed", opts: { name: "n", orderBy: "amount", value: "amount", agg: "sum", preceding: -1 } },
      /window fn 'framed' requires 'preceding' >= 0/,
    ],
    [
      "a desc list shorter than the order list",
      { fn: "row_number", opts: { name: "n", orderBy: ["region", "amount"], desc: [true] } },
      /window 'desc' must be an array of one boolean per 'orderBy' column \(2 expected, 1 given\)/,
    ],
    [
      "a partitionBy entry that is not a column name",
      { fn: "row_number", opts: { name: "n", orderBy: "amount", partitionBy: ["region", 1] } },
      "window 'partitionBy' takes column names; got 1",
    ],
    [
      "a partitionBy that is neither a name nor a list",
      { fn: "row_number", opts: { name: "n", orderBy: "amount", partitionBy: 7 } },
      "window 'partitionBy' must be a column name or a list of them",
    ],
  ] as const)("rejects %s", (_label, spec, message) => {
    const error = queryError(() => base().window(spec.fn as never, spec.opts as never));

    expect(error.code).toBe("invalid_arguments");
    expect(error.message).toMatch(message);
    expect(error.opIndex).toBe(0);
  });

  it("defaults a lag/lead offset to 1 when window() is called without one", () => {
    const [op] = ops(base().window("lead", { name: "next", orderBy: "amount", value: "amount" }));

    expect(op).toEqual({
      op: "window",
      fn: "lead",
      as: "next",
      nulls_last: true,
      order_by: ["amount"],
      value: "amount",
      offset: 1,
    });
  });

  it("emits partition_by, order_by, an expanded desc list and an explicit offset", () => {
    const [op] = ops(
      base().window("lag", {
        name: "previous",
        value: "amount",
        partitionBy: "region",
        orderBy: ["region", "amount"],
        desc: true,
        offset: 2,
        nullsLast: false,
      }),
    );

    expect(op).toEqual({
      op: "window",
      fn: "lag",
      as: "previous",
      nulls_last: false,
      partition_by: ["region"],
      order_by: ["region", "amount"],
      desc: [true, true],
      value: "amount",
      offset: 2,
    });
  });
});

describe("window sugar defaults", () => {
  it.each([
    [
      "rowNumber",
      (query: Query) => query.rowNumber({ name: "n", orderBy: "amount" }),
      { fn: "row_number", order_by: ["amount"] },
    ],
    [
      "rank",
      (query: Query) => query.rank({ name: "n", orderBy: "amount", partitionBy: ["region"] }),
      { fn: "rank", order_by: ["amount"], partition_by: ["region"] },
    ],
    [
      "denseRank",
      (query: Query) => query.denseRank({ name: "n", orderBy: "amount" }),
      { fn: "dense_rank", order_by: ["amount"] },
    ],
    [
      "lag",
      (query: Query) => query.lag("amount", { name: "n", orderBy: "amount" }),
      { fn: "lag", order_by: ["amount"], value: "amount", offset: 1 },
    ],
    [
      "lead (default offset)",
      (query: Query) => query.lead("amount", { name: "n", orderBy: "amount" }),
      { fn: "lead", order_by: ["amount"], value: "amount", offset: 1 },
    ],
    [
      "lead (explicit offset)",
      (query: Query) => query.lead("amount", { name: "n", orderBy: "amount", offset: 3 }),
      { fn: "lead", order_by: ["amount"], value: "amount", offset: 3 },
    ],
    [
      "running",
      (query: Query) => query.running("amount", { name: "n", orderBy: "amount", agg: "avg" }),
      { fn: "cumulative", order_by: ["amount"], value: "amount", agg: "avg" },
    ],
    [
      "rolling",
      (query: Query) => query.rolling("amount", { name: "n", orderBy: "amount", preceding: 2 }),
      { fn: "framed", order_by: ["amount"], value: "amount", agg: "sum", preceding: 2 },
    ],
    [
      "partitionTotal",
      (query: Query) => query.partitionTotal("amount", { name: "n", agg: "count" }),
      { fn: "partition_total", value: "amount", agg: "count" },
    ],
  ] as const)("%s spells the equivalent window op", (_name, build, expected) => {
    expect(ops(build(base()))).toEqual([{ op: "window", as: "n", nulls_last: true, ...expected }]);
  });
});
