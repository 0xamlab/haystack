---
icon: database
description: ClickHouse storage plane validation on a real race partition — measured codec choices (Delta beats DoubleDelta 1.8x), the sort-key trade-off, repeat-run semantics.
---

# Storage plane validation — measured, not assumed

ClickHouse 24.8.14.39 (pinned), loopback-bound, `f1_current` database, 14 tables.
Probe partition: Hungarian GP race 2026, `season=2026 session_key=11342`, 767,448 telemetry rows.

The plan required codecs be *benchmarked on representative partitions before applying them broadly*
rather than adopted on reputation. Doing that overturned one frozen choice and surfaced a second,
larger effect that is not about codecs at all.

---

## Result

| | on disk | B/row |
|---|---|---|
| Raw `CarData.z.jsonStream` (source, already compressed) | 6.53 MB | 8.51 |
| ClickHouse, frozen codecs (`DoubleDelta` on time) | 3.40 MiB | 4.64 |
| **ClickHouse, corrected codec (`Delta` on time)** | **2.43 MiB** | **3.32** |

ClickHouse ends up **2.7× smaller than the raw compressed feed** while being queryable columnar rather
than an opaque blob. Corpus projection: ~2.4 MiB per race session → ~90 MiB for the 2025–2026 race
sessions, low single-digit GB including practice, qualifying and earlier seasons.

## Per-column, after the correction

| column | codec | B/row | ratio |
|---|---|---:|---:|
| `event_time` | Delta + ZSTD(3) | 1.611 | — |
| `rpm` | Delta + ZSTD(3) | 0.619 | 3.2× |
| `speed_kph` | Delta + ZSTD(3) | 0.35 | 5.8× |
| `throttle_pct` | T64 + ZSTD(3) | 0.31 | 6.5× |
| `brake` | T64 + ZSTD(3) | 0.149 | 13.4× |
| `gear` | T64 + ZSTD(3) | 0.11 | 9.2× |
| `repeat_run_length` | T64 + ZSTD(3) | 0.12 | 8.1× |
| `source_sequence` | DoubleDelta + ZSTD(3) | 0.01 | **817×** |
| `season` / `session_key` / `car_number` | T64 + ZSTD(3) | 0.01–0.02 | 181–223× |

`source_sequence` at 817× vindicates carrying it: it is monotonic by 1 within a part, so DoubleDelta
renders it essentially free. The mandatory ordering tie-break costs nothing.

---

## Correction 1 — `Delta`, not `DoubleDelta`, for timestamps

Measured on the real partition, event_time only:

| codec | B/row (event_time-sorted) | B/row (car-sorted) |
|---|---:|---:|
| **Delta + ZSTD(3)** | **0.161** | **1.611** |
| Delta + ZSTD(9) | 0.157 | — |
| ZSTD(3) alone | 0.237 | 5.162 |
| DoubleDelta + ZSTD(3) | 0.281 | 2.943 |
| T64 + ZSTD(3) | 0.594 | — |
| none | 8.005 | — |

**DoubleDelta is the wrong choice here and plain ZSTD beat it in one ordering.** DoubleDelta encodes
second differences and pays off when the interval is near-constant — a regular clock. This feed is
irregular: p50 0.240 s, p90 0.400 s, max 1.521 s. Delta wins by **1.8×**.

Applied. This is a direct, quantified consequence of the irregular-sampling finding: an assumption that
looked safe on reputation was wrong for this data, and only measurement showed it.

`Gorilla` is unsupported on `DateTime64` — confirmed, not assumed.

---

## Finding 2 — the sort key matters ~10×, and this one is a real trade-off

`event_time` cost swings by an order of magnitude with the sort key, because **all 22 cars share each
frame timestamp**. Ordering by `event_time` first makes consecutive rows carry *identical* timestamps,
so deltas are mostly zero. Ordering by `car_number` first leaves consecutive deltas at ~0.24 s with
jitter — non-zero and noisy.

Measured on a 5-column table with corrected codecs:

| ORDER BY | table size | one car's trace | time-window scan | group-by-car |
|---|---:|---:|---:|---:|
| `(car_number, event_time, source_sequence)` — frozen | 1,996,100 B | **3.1 ms** | 3.6 ms | **3.4 ms** |
| `(event_time, car_number, source_sequence)` | **1,077,254 B** (1.85× smaller) | 10.5 ms | **2.6 ms** | 11.0 ms |

**Not applied — flagged for decision**, because the frozen spec specifies `car_number` first and this
is a genuine judgment call rather than a clear error.

The case for changing it: 1.85× smaller, faster time-window scans, and — the strongest argument —
Invariant 4's as-of replay processes events strictly in `(event_time, source_sequence)` order, so
time-first matches the critical-path access pattern.

The case for keeping it: per-car traces are 3.4× slower, and those are what the Gate 5 telemetry proxies
need. Against that, every measured query is between 2.6 and 11 ms on 767k rows, so neither ordering is
anywhere near a bottleneck at this scale.

A projection or skip index could recover per-car performance under time-first ordering if the storage
win is judged worth having.

---

## Applied semantics confirmed on load

| | count | share |
|---|---:|---:|
| rows | 767,448 | |
| `throttle_pct` NULL (104 staleness) | 89,578 | 11.7% |
| `brake` NULL (104 staleness) | 183,164 | 23.9% |
| repeated `(rpm, speed, gear)` triples | **495,708** | **64.6%** |

That last row is the one to keep in view: **64.6% of samples repeat the previous `(rpm, speed, gear)`
triple with no staleness marker at all.** Explicit missingness on throttle and brake is the easy case —
the invisible kind is far more common. `repeat_run_length` exists so downstream can tell a stale value
from a genuinely constant one; without it, any derivative computed across repeats yields spurious zeros.

Round-trip verified: 767,448 rows, 22 cars, span `12:09:11.245644700` → `14:46:16.958452900` — the
7-fractional-digit source precision preserved exactly by `DateTime64(9)`.

---

## Deliberately absent

**No TTL.** The retention matrix depends on a legal finding that is still pending. Inventing a period
now would be a guess dressed as policy. TTL arrives as `ALTER TABLE ... MODIFY TTL` alongside the
deletion-manifest job that proves removal of the external artifacts ClickHouse TTL cannot reach.

## Related

* [DATA_SOURCES.md](DATA_SOURCES.md) — the feeds this storage plane persists.
* [FROZEN_SPECS.md](FROZEN_SPECS.md) — the frozen codec and sort-key choices validated here.
* [GATE0_VERIFICATION.md](GATE0_VERIFICATION.md) — the Gate 0 record this validation supports.
