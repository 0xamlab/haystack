// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from "vitest";

import { Query, QueryError, QueryResult, caseWhen, col, lit } from "./query.js";

describe("Query construction", () => {
  it("requires a non-empty columns list", () => {
    expect(() => new Query({ columns: [], rows: [[1]] })).toThrowError(
      "a query needs a non-empty columns list",
    );
  });

  it("requires rows or a dataset, not neither", () => {
    expect(() => new Query({ columns: ["a"] })).toThrowError(
      "a query needs either rows or a dataset handle",
    );
  });

  it("requires rows or a dataset, not both", () => {
    expect(() => new Query({ columns: ["a"], rows: [[1]], dataset: "ds_1" })).toThrowError(
      "pass rows OR dataset, not both",
    );
  });

  it("normalizes booleans and nulls in rows to the wire's numeric-or-null cells", () => {
    const request = new Query({ columns: ["a", "b"], rows: [[true, null], [false, 2]] })
      .select("a")
      .toRequest();
    expect(request.rows).toEqual([[1, null], [0, 2]]);
  });

  it("rejects a row wider than the header", () => {
    expect(() => new Query({ columns: ["a"], rows: [[1, 2]] })).toThrowError(
      /has 2 values but the header declares 1 columns/,
    );
  });
});

describe("filter / project / select / sort / distinct / limit / topK wire shape", () => {
  it("filter flattens a predicate into a postorder node array", () => {
    const query = new Query({ columns: ["amount"], rows: [[10]] }).filter(col("amount").gt(20));
    const request = query.toRequest();
    const op = (request.ops as Array<Record<string, unknown>>)[0];
    expect(op.op).toBe("filter");
    const predicate = op.predicate as { nodes: unknown[]; root: number };
    expect(predicate.nodes.length).toBe(3); // col ref, literal, gt
    expect(predicate.root).toBe(2);
  });

  it("project rejects an empty expression set", () => {
    expect(() => new Query({ columns: ["a"], rows: [[1]] }).project({})).toThrowError(
      "project needs at least one expression",
    );
  });

  it("select rejects an empty name list", () => {
    expect(() => new Query({ columns: ["a"], rows: [[1]] }).select()).toThrowError(
      "select needs at least one column name",
    );
  });

  it("sort rejects a list desc against a scalar by", () => {
    expect(() =>
      new Query({ columns: ["a"], rows: [[1]] }).sort("a", { desc: [true] as unknown as boolean }),
    ).toThrowError("desc may only be a list when 'by' is a list");
  });

  it("groupBy rejects an unknown aggregation", () => {
    expect(() =>
      new Query({ columns: ["a", "b"], rows: [[1, 2]] }).groupBy("a", "b", { agg: "median" as never }),
    ).toThrowError(/unknown aggregation 'median'/);
  });

  it("topK and limit reject a value that is not a safe integer", () => {
    const unsafe = Number.MAX_SAFE_INTEGER + 10;
    expect(() => new Query({ columns: ["a"], rows: [[1]] }).topK("a", unsafe)).toThrowError(QueryError);
    expect(() => new Query({ columns: ["a"], rows: [[1]] }).limit(unsafe)).toThrowError(QueryError);
    expect(() => new Query({ columns: ["a"], rows: [[1]] }).limit(3.5)).toThrowError(QueryError);
  });
});

describe("withTable", () => {
  it("rejects a table declared twice", () => {
    const query = new Query({ columns: ["a"], rows: [[1]] }).withTable("t", ["id"], { rows: [[1]] });
    expect(() => query.withTable("t", ["id"], { rows: [[2]] })).toThrowError("table 't' is declared twice");
  });

  it("rejects neither rows nor dataset, and both rows and dataset", () => {
    const query = new Query({ columns: ["a"], rows: [[1]] });
    expect(() => query.withTable("t", ["id"])).toThrowError(/needs exactly one of rows or dataset/);
    expect(() => query.withTable("t2", ["id"], { rows: [[1]], dataset: "ds" })).toThrowError(
      /needs exactly one of rows or dataset/,
    );
  });
});

describe("join", () => {
  const base = () => new Query({ columns: ["order_id", "customer_id"], rows: [[1, 10]] });

  it("builds the exact wire op shape for the common case", () => {
    const request = base()
      .withTable("customers", ["id", "tier"], { rows: [[10, 1]] })
      .join("customers", { leftOn: "customer_id", rightOn: "id", how: "left" })
      .toRequest();
    expect(request.ops).toEqual([
      { op: "join", table: "customers", left_on: "customer_id", right_on: "id", how: "left", method: "hash" },
    ]);
    expect(request.tables).toEqual([{ name: "customers", columns: ["id", "tier"], rows: [[10, 1]] }]);
  });

  it("resolves the 'on' shorthand to matching left_on/right_on", () => {
    const query = base().withTable("c", ["order_id"], { rows: [[1]] }).join("c", { on: "order_id" });
    const op = query.toRequest().ops as Array<Record<string, unknown>>;
    expect(op[0].left_on).toBe("order_id");
    expect(op[0].right_on).toBe("order_id");
  });

  it("rejects a mix of on and one-sided keys", () => {
    expect(() =>
      base().withTable("c", ["id"], { rows: [[1]] }).join("c", { on: "order_id", rightOn: "id" }),
    ).toThrowError(/not a mix/);
  });

  it("rejects right, outer, full and cross by name", () => {
    for (const how of ["right", "outer", "full", "cross"] as const) {
      expect(() =>
        base()
          .withTable("c", ["id"], { rows: [[1]] })
          .join("c", { on: "order_id", how: how as never }),
      ).toThrowError(/not implemented/);
    }
  });

  it("rejects an unknown join method and lists the real three", () => {
    expect(() =>
      base().withTable("c", ["id"], { rows: [[1]] }).join("c", { on: "order_id", method: "sortmerge" as never }),
    ).toThrowError("hash, merge or direct_address");
  });

  it("rejects a merge or direct_address semi/anti join rather than silently using hash", () => {
    for (const method of ["merge", "direct_address"] as const) {
      expect(() =>
        base()
          .withTable("c", ["id"], { rows: [[1]] })
          .join("c", { on: "order_id", how: "semi", method }),
      ).toThrowError(`join method '${method}' is not defined for how 'semi'`);
    }
  });

  it("rejects a prefix on a semi/anti join since it emits no right columns", () => {
    expect(() =>
      base().withTable("c", ["id"], { rows: [[1]] }).join("c", { on: "order_id", how: "anti", prefix: "c." }),
    ).toThrowError(/no right columns/);
  });

  it("rejects an empty prefix as unexpressible", () => {
    expect(() =>
      base().withTable("c", ["id"], { rows: [[1]] }).join("c", { on: "order_id", prefix: "" }),
    ).toThrowError(/empty join prefix is not expressible/);
  });

  it("toRequest catches a join referencing an undeclared table, naming what IS available", () => {
    const query = base().withTable("customers", ["id"], { rows: [[10]] }).join("orders", { on: "order_id" });
    expect(() => query.toRequest()).toThrowError(/references table 'orders'.*available: customers/s);
  });

  it("accepts method=\"direct_address\" on the wire (the engine, not the builder, verifies the shape)", () => {
    const request = base()
      .withTable("customers", ["id"], { rows: [[10]] })
      .join("customers", { leftOn: "customer_id", rightOn: "id", method: "direct_address" })
      .toRequest();
    expect((request.ops as Array<Record<string, unknown>>)[0].method).toBe("direct_address");
  });
});

describe("union", () => {
  it("requires at least one table name", () => {
    expect(() => new Query({ columns: ["a"], rows: [[1]] }).union()).toThrowError(
      "union needs at least one table name",
    );
  });

  it("toRequest catches a union referencing an undeclared table", () => {
    const query = new Query({ columns: ["a"], rows: [[1]] }).union("missing");
    expect(() => query.toRequest()).toThrowError(/union references table 'missing'/);
  });
});

describe("window", () => {
  const base = () => new Query({ columns: ["region", "amount"], rows: [[1, 10]] });

  it("requires a non-empty output name", () => {
    expect(() =>
      base().window("row_number", { name: "", orderBy: "amount" }),
    ).toThrowError("window requires 'name'");
  });

  it("requires order_by for functions that need it", () => {
    expect(() => base().window("rank", { name: "r", orderBy: [] })).toThrowError(
      /requires a non-empty 'orderBy'/,
    );
  });

  it("requires exactly one order column for rank/dense_rank", () => {
    expect(() =>
      base().window("rank", { name: "r", orderBy: ["amount", "region"] }),
    ).toThrowError(/requires exactly one 'orderBy' column/);
  });

  it("lag/lead require 'value' and reject offset < 1", () => {
    expect(() => base().window("lag", { name: "l", orderBy: "amount", offset: 0, value: "amount" })).toThrowError(
      /requires 'offset' >= 1/,
    );
  });

  it("framed requires a non-negative preceding, and cumulative takes none", () => {
    expect(() =>
      base().window("framed", { name: "f", orderBy: "amount", value: "amount", agg: "sum" }),
    ).toThrowError(/requires 'preceding' >= 0/);
    expect(() =>
      base().window("cumulative", { name: "c", orderBy: "amount", value: "amount", agg: "sum", preceding: 1 }),
    ).toThrowError(/takes no 'preceding'/);
  });

  it("the sugar methods emit the same op shape window() would", () => {
    const viaSugar = base()
      .running("amount", { name: "running_total", orderBy: "amount" })
      .toRequest().ops as Array<Record<string, unknown>>;
    const viaWindow = base()
      .window("cumulative", { name: "running_total", orderBy: "amount", value: "amount", agg: "sum" })
      .toRequest().ops as Array<Record<string, unknown>>;
    expect(viaSugar).toEqual(viaWindow);
  });

  it("partitionTotal takes no order_by since it is order-independent", () => {
    const op = base()
      .partitionTotal("amount", { name: "share", partitionBy: "region" })
      .toRequest().ops as Array<Record<string, unknown>>;
    expect(op[0]).toEqual({
      op: "window",
      fn: "partition_total",
      as: "share",
      nulls_last: true,
      partition_by: ["region"],
      value: "amount",
      agg: "sum",
    });
  });
});

describe("caseWhen / Expr", () => {
  it("builds a chain of ternary nodes, innermost first", () => {
    const expr = caseWhen([[col("x").gt(0), lit(1)], [col("x").lt(0), lit(-1)]], lit(0));
    const plan = expr.toPlan();
    // 2 branches x 3 nodes (cond, then, else-so-far) + the base else literal = 7 nodes
    expect(plan.nodes.length).toBeGreaterThan(0);
    expect(plan.root).toBe(plan.nodes.length - 1);
  });

  it("caseWhen requires at least one branch", () => {
    expect(() => caseWhen([], lit(0))).toThrowError("caseWhen needs at least one");
  });
});

describe("QueryResult", () => {
  it("column() returns one output column by name, and throws for an unknown one", () => {
    const result = new QueryResult({
      columns: ["a", "b"],
      rows: [[1, 2], [3, null]],
      lineage: [],
      planHash: "x",
      ops: 1,
      latencyMs: 1,
    });
    expect(result.column("b")).toEqual([2, null]);
    expect(() => result.column("z")).toThrowError(/has no column 'z'/);
  });

  it("toDicts() zips columns with each row", () => {
    const result = new QueryResult({
      columns: ["a", "b"],
      rows: [[1, 2]],
      lineage: [],
      planHash: "x",
      ops: 1,
      latencyMs: 1,
    });
    expect(result.toDicts()).toEqual([{ a: 1, b: 2 }]);
  });
});
