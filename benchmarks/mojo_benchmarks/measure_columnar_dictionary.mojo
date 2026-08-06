"""
measure_columnar_dictionary.mojo — what dictionary encoding actually costs and saves.

Two numbers, both measured, neither assumed:

  1. FOOTPRINT, priced in Arrow's layout by `dictionary.footprint`, swept over
     cardinality at a fixed row count. The sweep is the honest form: the ratio crosses
     1.0 somewhere, and printing where means nobody has to take "dictionary encoding
     shrinks the column" on faith.
  2. THROUGHPUT of encode and decode in ns/row, so the saving has a price attached.

Named `measure_*` rather than `bench_*`: `tests/benchmark_mojo_vs_python.py` generates
`bench_{module}.mojo` into this directory and would overwrite a hand-written file there.

Compiled, not JIT (rule 1b):

    cd mojo_env
    pixi run mojo build -I../mojo/engine \\
        ../benchmarks/mojo_benchmarks/measure_columnar_dictionary.mojo \\
        -o /tmp/measure_dictionary
    /tmp/measure_dictionary

Correctness is gated before any timing: at every point in the sweep the decoded column
must equal the original exactly, nulls included. A throughput number for a wrong answer
is not a throughput number.
"""
from std.time import perf_counter_ns

from columnar.dictionary import (
    DICT_OK,
    NULL_CODE,
    decode_strings,
    dict_status_name,
    encode_strings,
    footprint,
)


def build_column(n_rows: Int, n_distinct: Int, label_bytes: Int) -> List[String]:
    """`n_rows` rows drawn round-robin from `n_distinct` labels of `label_bytes` bytes.

    Round-robin rather than random so the column, the dictionary and therefore every
    number below is reproducible run to run.
    """
    var labels = List[String]()
    for d in range(n_distinct):
        var label = String("label-") + String(d)
        while len(label.as_bytes()) < label_bytes:
            label += "x"
        labels.append(label)
    var out = List[String]()
    for i in range(n_rows):
        out.append(labels[i % n_distinct])
    return out^


def build_mask(n_rows: Int) -> List[Bool]:
    """Every seventh row absent, so nulls are exercised at every size."""
    var mask = List[Bool]()
    for i in range(n_rows):
        mask.append(i % 7 != 0)
    return mask^


def expected_distinct(n_rows: Int, n_distinct: Int, mask: List[Bool]) -> Int:
    """Labels that appear in at least one PRESENT row.

    Not `n_distinct`. An absent row contributes nothing to the dictionary, so when the
    row count equals the label count every label appears exactly once and the ~1-in-7
    that land on a null row are absent from the dictionary entirely: at 200 000 rows and
    200 000 labels the answer is 171 428, not 200 000. The gate below asserted the naive
    value first and caught this, which is what a gate is for.
    """
    var seen = List[Bool]()
    for _ in range(n_distinct):
        seen.append(False)
    var total = 0
    for i in range(n_rows):
        if i < len(mask) and mask[i]:
            var label = i % n_distinct
            if not seen[label]:
                seen[label] = True
                total += 1
    return total


def main():
    print("measure_columnar_dictionary — footprint sweep and throughput, compiled")
    print("")

    comptime N_ROWS: Int = 200000
    comptime LABEL_BYTES: Int = 20
    comptime REPEATS: Int = 3

    var cardinalities = List[Int]()
    cardinalities.append(5)
    cardinalities.append(50)
    cardinalities.append(500)
    cardinalities.append(5000)
    cardinalities.append(50000)
    cardinalities.append(200000)

    print(
        "  "
        + String(N_ROWS)
        + " rows, "
        + String(LABEL_BYTES)
        + "-byte labels, every 7th row null"
    )
    print("  labels | in dict |   plain B |  coded B | ratio | encode ns/row | decode ns/row")

    var failures = 0
    for c in range(len(cardinalities)):
        var n_distinct = cardinalities[c]
        var values = build_column(N_ROWS, n_distinct, LABEL_BYTES)
        var mask = build_mask(N_ROWS)

        # ── gate ──────────────────────────────────────────────────────────────
        var encoded = encode_strings(values, mask)
        var decoded = decode_strings(
            encoded.dictionary, encoded.codes, encoded.validity, encoded.n_rows
        )
        var exact = (
            encoded.status == DICT_OK
            and decoded.status == DICT_OK
            and decoded.n_rows == N_ROWS
            and encoded.n_distinct == expected_distinct(N_ROWS, n_distinct, mask)
        )
        if exact:
            for i in range(N_ROWS):
                if mask[i]:
                    if not decoded.mask[i] or decoded.values[i] != values[i]:
                        exact = False
                        break
                else:
                    if decoded.mask[i] or encoded.codes[i] != NULL_CODE:
                        exact = False
                        break
        if not exact:
            print(
                "  ❌ distinct="
                + String(n_distinct)
                + " round trip is not exact ("
                + dict_status_name(decoded.status)
                + ") — no timings"
            )
            failures += 1
            continue

        var measured = footprint(values, mask)

        var encode_ns = 0.0
        var decode_ns = 0.0
        for _ in range(REPEATS):
            var t0 = perf_counter_ns()
            var e = encode_strings(values, mask)
            var t1 = perf_counter_ns()
            var elapsed_encode = Float64(Int(t1 - t0))
            if encode_ns == 0.0 or elapsed_encode < encode_ns:
                encode_ns = elapsed_encode

            var t2 = perf_counter_ns()
            var d = decode_strings(e.dictionary, e.codes, e.validity, e.n_rows)
            var t3 = perf_counter_ns()
            var elapsed_decode = Float64(Int(t3 - t2))
            if decode_ns == 0.0 or elapsed_decode < decode_ns:
                decode_ns = elapsed_decode
            if d.n_rows != N_ROWS:
                failures += 1

        print(
            "  "
            + String(n_distinct)
            + " | "
            + String(measured.n_distinct)
            + " | "
            + String(measured.plain_bytes)
            + " | "
            + String(measured.encoded_bytes)
            + " | "
            + String(measured.ratio)
            + " | "
            + String(encode_ns / Float64(N_ROWS))
            + " | "
            + String(decode_ns / Float64(N_ROWS))
        )

    if failures == 0:
        print("")
        print("  [columnar.dictionary] every point in the sweep round-tripped exactly")
    else:
        print("  [columnar.dictionary] FAILURES:", failures)
