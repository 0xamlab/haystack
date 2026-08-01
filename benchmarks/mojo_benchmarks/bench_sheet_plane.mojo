"""bench_sheet_plane.mojo — measured gate for the `sheet` package.

Synthesizes workbooks in memory (a dependency chain emitted deepest-first, a
fan-in of SUM/COUNTIF aggregates, and a VLOOKUP table walk), recalcs them
through the same `sheet_recalc_report` entry the corpus validation uses, and
gates on PROPERTIES, never on absolute nanoseconds:

  1. CORRECTNESS SENTINEL — every synthesized cell carries a hand-derivable
     cached value and must match EXACTLY. Fast wrong answers are the failure
     mode a spreadsheet benchmark invites; a single mismatch fails the gate,
     so the throughput printed below is throughput of verified-correct work.
  2. DETERMINISM — the same workbook recalculated twice reports identical
     counts and an identical probe value, bit for bit ("same workbook, same
     recalc, bit-identical, twice").
  3. SCALING — recalc cost per formula cell across an 8x rise in chain length
     stays within 6x (the traversal is O(cells); a superlinear engine shows
     up here long before it shows up as a hang on finch's million-row
     columns).
  4. CHARGED WORK — the ops counter must grow with the work (>= 1 op per
     formula cell) and stay within 64x of linear on the chain, or the budget
     is not measuring what it spends.

Throughput (formula cells / second) is printed as information.

Run:
    cd mojo_env && pixi run mojo run -I../mojo/engine \
        ../benchmarks/mojo_benchmarks/bench_sheet_plane.mojo
"""

from time import perf_counter_ns

from sheet.api import sheet_eval_cell, sheet_recalc_report


fn _chain_workbook(n: Int) -> String:
    """A1=1; A<i> = A<i-1>+1 emitted DEEPEST-FIRST so the demand stack walks
    the whole chain; cached values are exact integers."""
    var t = String("SHEETWB\t1\nD\t0\nS\tS\n")
    t += "C\t0\tA1\tn\t1\n"
    var i = n
    while i >= 2:
        t += "F\t0\tA"
        t += String(i)
        t += "\tn\tA"
        t += String(i - 1)
        t += "+1\tn\t"
        t += String(i)
        t += "\n"
        i -= 1
    return t^


fn _agg_workbook(rows: Int) -> String:
    """B column of constants 1..rows, then SUM/COUNTIF/MIN/MAX over the whole
    column plus a VLOOKUP per tenth row. All cached values in closed form."""
    var t = String("SHEETWB\t1\nD\t0\nS\tS\n")
    for i in range(1, rows + 1):
        t += "C\t0\tB"
        t += String(i)
        t += "\tn\t"
        t += String(i)
        t += "\n"
    # SUM(B1:B<rows>) = rows*(rows+1)/2
    t += "F\t0\tD1\tn\tSUM(B1:B"
    t += String(rows)
    t += ")\tn\t"
    t += String(rows * (rows + 1) // 2)
    t += "\n"
    t += "F\t0\tD2\tn\tCOUNTIF(B1:B"
    t += String(rows)
    t += ",\">10\")\tn\t"
    t += String(rows - 10 if rows > 10 else 0)
    t += "\n"
    t += "F\t0\tD3\tn\tMIN(B1:B"
    t += String(rows)
    t += ")\tn\t1\n"
    t += "F\t0\tD4\tn\tMAX(B1:B"
    t += String(rows)
    t += ")\tn\t"
    t += String(rows)
    t += "\n"
    var k = 10
    var slot = 5
    while k <= rows:
        t += "F\t0\tD"
        t += String(slot)
        t += "\tn\tVLOOKUP("
        t += String(k)
        t += ",B1:B"
        t += String(rows)
        t += ",1,FALSE)\tn\t"
        t += String(k)
        t += "\n"
        k += 10
        slot += 1
    return t^


fn main() raises:
    var failures = 0

    # ── arm 1+2: correctness sentinel + determinism on the aggregate book ───
    var agg = _agg_workbook(2000)
    var r1 = sheet_recalc_report(agg, 0)
    var r2 = sheet_recalc_report(agg, 0)
    var total1 = r1.matched_exact
    if r1.status != 1320 or r1.mismatched != 0 or r1.error_mismatched != 0 or r1.unsupported != 0:
        failures += 1
        print("  ❌ aggregate sentinel: mismatches on hand-derivable values:", r1.mismatch_samples)
    else:
        print("  ✅ aggregate sentinel:", total1, "cells all exact (SUM/COUNTIF/MIN/MAX/VLOOKUP)")
    var p1 = sheet_eval_cell(agg, String("S"), String("D1"), 0)
    var p2 = sheet_eval_cell(agg, String("S"), String("D1"), 0)
    if r1.matched_exact != r2.matched_exact or r1.ops != r2.ops or p1.num != p2.num:
        failures += 1
        print("  ❌ determinism: two recalcs disagree")
    else:
        print("  ✅ determinism: recalc twice -> identical counts, identical bits, identical ops")

    # ── arm 3+4: chain scaling, 8x rise ──────────────────────────────────────
    var small_n = 4000
    var big_n = 32000
    var small = _chain_workbook(small_n)
    var big = _chain_workbook(big_n)
    var t0 = perf_counter_ns()
    var rs = sheet_recalc_report(small, 0)
    var t1 = perf_counter_ns()
    var rb = sheet_recalc_report(big, 0)
    var t2 = perf_counter_ns()
    var ok_small = rs.matched_exact == small_n - 1 and rs.mismatched == 0
    var ok_big = rb.matched_exact == big_n - 1 and rb.mismatched == 0
    if not ok_small or not ok_big:
        failures += 1
        print("  ❌ chain sentinel: ", rs.matched_exact, rb.matched_exact, rb.mismatch_samples)
    else:
        print("  ✅ chain sentinel: both chains fully exact, depth", rb.max_chain)
    var ns_small = Float64(Int(t1 - t0))
    var ns_big = Float64(Int(t2 - t1))
    var per_small = ns_small / Float64(small_n)
    var per_big = ns_big / Float64(big_n)
    var growth = per_big / per_small if per_small > 0.0 else 1e9
    if growth > 6.0:
        failures += 1
        print("  ❌ scaling: per-cell cost grew", growth, "x across an 8x size rise")
    else:
        print("  ✅ scaling: per-cell cost ratio at 8x size =", growth, "x (gate: <= 6)")
    if rb.ops < big_n or rb.ops > 64 * big_n:
        failures += 1
        print("  ❌ charged work off scale: ops =", rb.ops, "for", big_n, "cells")
    else:
        print("  ✅ charged work:", rb.ops, "ops for", big_n, "formula cells")
    var cells_per_sec = Float64(big_n) / (ns_big / 1e9)
    print("  ℹ️ chain throughput:", Int(cells_per_sec), "formula cells/sec (JIT; info only)")

    if failures == 0:
        print("BENCH_GATE sheet_plane PASS")
    else:
        print("BENCH_GATE sheet_plane FAIL " + String(failures))
        raise Error("bench_sheet_plane: " + String(failures) + " gate failure(s)")
