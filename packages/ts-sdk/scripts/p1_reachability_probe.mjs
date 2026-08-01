#!/usr/bin/env node
/**
 * Execute one function from each of the twelve P1 analytical families through the TypeScript
 * MojoRuntime and print what came back.
 *
 * This is the executed half of the reachability claim. `src/libraries_p1_families.test.ts`
 * proves the catalog RESOLVES each family from the generated runtime contract without a runtime
 * present; this script proves the resolved call RUNS and returns a value, which a resolution
 * test cannot show. Run it against a local runtime:
 *
 *     node packages/ts-sdk/scripts/p1_reachability_probe.mjs
 *
 * It needs `npm run build` first (it imports the built `dist/`), and a local runtime reachable
 * at ALGENTA_DAEMON_TCP (default 127.0.0.1:50099). Every argument below is chosen so the
 * expected answer is checkable by hand; the expectations are printed beside the results and are
 * asserted, so a wrong number is a non-zero exit and not a line of output somebody has to read.
 */
import { MojoRuntime } from "../dist/index.js";

const CASES = [
  {
    family: "forecasting",
    module: "forecasting.point",
    fn: "ets_ann_forecast",
    args: [[10, 10, 10, 10, 10], 0.5, 2],
    // Simple exponential smoothing of a constant series is that constant, at every horizon.
    check: r => r.status_name === "ok" && r.values.length === 2
      && Math.abs(r.values[0] - 10) < 1e-12 && Math.abs(r.values[1] - 10) < 1e-12,
    expect: "level 10 held flat over both horizons",
  },
  {
    family: "inference",
    module: "inference.core",
    fn: "inference_t_sf_two_sided",
    args: [2.0, 10.0],
    // P(|T_10| >= 2) = 0.07338788286251831.
    check: r => Math.abs(r - 0.07338788286251831) < 1e-6,
    expect: "0.0733878828625 (two-sided t tail, df = 10)",
  },
  {
    family: "causal_inference",
    module: "causal_inference.estimators",
    fn: "naive_ate",
    args: [[7, 2, 10, 5], [1, 0, 1, 0]],
    // (7 + 10)/2 - (2 + 5)/2 = 8.5 - 3.5 = 5.
    check: r => r.has_diff && Math.abs(r.diff - 5) < 1e-12,
    expect: "treated-minus-control difference exactly 5",
  },
  {
    family: "survival_analysis",
    module: "survival_analysis.km",
    fn: "km_fit",
    args: [[1, 2, 3, 4], [1, 1, 1, 1], 0.95],
    // Four uncensored events: S drops 1 -> 3/4 -> 1/2 -> 1/4 -> 0.
    check: r => r.survival.length === 4 && Math.abs(r.survival[0] - 0.75) < 1e-12
      && Math.abs(r.survival[3] - 0.0) < 1e-12,
    expect: "survival 0.75, 0.5, 0.25, 0",
  },
  {
    family: "streaming",
    module: "streaming.quantiles",
    fn: "quantile_ingest",
    args: [[1, 2, 3, 4, 5, 6, 7, 8], 64, 7],
    check: r => r.n === 8,
    expect: "a sketch holding all 8 observations",
  },
  {
    family: "geospatial",
    module: "geospatial.polygon",
    fn: "ring_area_flat",
    // frame 2 is GEO_FRAME_PLANE_M — metres, not degrees. A 4x3 rectangle.
    args: [[0, 4, 4, 0], [0, 0, 3, 3], 4, 2],
    check: r => r.has_area && Math.abs(Math.abs(r.area_m2) - 12) < 1e-12,
    expect: "|area| exactly 12 m^2",
  },
  {
    family: "discrete_event",
    module: "discrete_event.queue_sim",
    fn: "qs_closed_form_flat",
    // capacity 1 is M/M/1. At rho = 0.5, L = rho/(1 - rho) = 1 and Lq = rho^2/(1 - rho) = 0.5.
    args: [1.0, 2.0, 1],
    check: r => r.exists && Math.abs(r.number_in_system - 1.0) < 1e-12
      && Math.abs(r.number_in_queue - 0.5) < 1e-12,
    expect: "L = 1 and Lq = 0.5 for M/M/1 at rho = 0.5",
  },
  {
    family: "evaluation",
    module: "evaluation.scores",
    fn: "log_loss_flat",
    args: [[0.5, 0.5, 0.5, 0.5], [1, 0, 1, 0], 4],
    // -ln(0.5) for every observation.
    check: r => r.present && Math.abs(r.log_loss - Math.LN2) < 1e-12,
    expect: "ln 2 = 0.6931471805599453",
  },
  {
    family: "data_quality",
    module: "data_quality.profile",
    fn: "profile_column",
    // the mask marks PRESENT rows, so all-true is a column with no nulls
    args: [[1, 2, 3, 4], [true, true, true, true], 4],
    check: r => r.has_mean && Math.abs(r.mean - 2.5) < 1e-12 && r.n_null === 0 && r.n_present === 4,
    expect: "mean 2.5 over 4 present rows, zero nulls",
  },
  {
    family: "strategy",
    module: "strategy.equilibrium",
    fn: "eq_exploitability_flat",
    args: [[1, -1, -1, 1, -1, 1, 1, -1], 2, 2, [0.5, 0.5, 0.5, 0.5], 1e-12],
    // Matching pennies at the uniform mixture: the equilibrium, so exploitability is 0.
    check: r => r.has_residual && Math.abs(r.residual) < 1e-12 && r.is_equilibrium,
    expect: "residual exactly 0 and is_equilibrium at the matching-pennies mixture",
  },
  {
    family: "sparse_numerics",
    module: "sparse_numerics.spmv",
    fn: "spmv_frobenius_norm_driver",
    args: [[0, 1, 2], [0, 1], [3, 4], 2, 2],
    // diag(3, 4): sqrt(9 + 16) = 5.
    check: r => Math.abs(r.value - 5) < 1e-12,
    expect: "Frobenius norm exactly 5",
  },
  {
    family: "graph_analytics",
    module: "graph_analytics.centrality",
    fn: "graph_degree_centrality",
    args: [[0, 2, 3, 4], [1, 2, 0, 0], [1, 1, 1, 1], 3, false],
    check: r => r.out_values.length === 3 && Math.abs(r.out_values[0] - 2) < 1e-12
      && Math.abs(r.out_values[1] - 1) < 1e-12,
    expect: "out-degree 2 for node 0 and 1 for node 1",
  },
];

async function main() {
  const runtime = new MojoRuntime();
  const health = await runtime.health();
  console.log(
    `runtime: status=${health.status} engine=${health.engine} modules=${health.module_count}`,
  );
  if (!health.runtime_available) {
    console.error("no local runtime is reachable; start one and re-run");
    process.exitCode = 2;
    return;
  }

  const catalog = await runtime.libraries();
  let failures = 0;
  for (const testCase of CASES) {
    const started = process.hrtime.bigint();
    let result;
    try {
      result = await catalog.module(testCase.module)[testCase.fn](...testCase.args);
    } catch (error) {
      failures += 1;
      console.log(`${testCase.family.padEnd(18)} FAILED  ${String(error)}`);
      continue;
    }
    const elapsedMs = Number(process.hrtime.bigint() - started) / 1e6;
    const ok = testCase.check(result);
    if (!ok) failures += 1;
    console.log(
      `${testCase.family.padEnd(18)} ${(ok ? "ok" : "WRONG").padEnd(6)} ` +
        `${testCase.module}.${testCase.fn}  ${elapsedMs.toFixed(2)} ms\n` +
        `${" ".repeat(20)}expected ${testCase.expect}\n` +
        `${" ".repeat(20)}returned ${JSON.stringify(result)}`,
    );
  }
  console.log(`\n${CASES.length - failures}/${CASES.length} families returned the expected value`);
  if (failures > 0) process.exitCode = 1;
}

await main();
