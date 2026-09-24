# Benchmark rulebook v0.6

The measurement protocol the fleet's timed cells run under — the Try tab's hero z-test and
every Races cell. (The LLM kernel panels share the card, the hardware footer and the parity
chip but time their own way — one warm-up, then `llm_tab.REPEATS` = 5 calls per lane, printed
as `n = 5`, labelled "not a race" with no ratio; measured on the deployed build, 2026-09-23.)
The code is
`apps/spaces/_shared/algenta_spaces/bench.py` (`run_cell`); the card that prints it is
`apps/spaces/_shared/algenta_spaces/cards.py`. Every constant below is printed on the card or
in its How-measured disclosure: a rule that is not on the card is not a rule.

## The protocol

1. **Correctness gate first.** Every lane runs once; the cell's gate compares the outputs
   (exact match, a tolerance, or a reference library such as statsmodels). A gate that does
   not agree holds the cell (`gate_failed`) and nothing is timed.
2. **Two discarded warm-ups** per lane, interleaved.
3. **N = 21 interleaved round-robin samples per lane** when the slowest lane's fastest
   warm-up call takes under 250 ms, else N = 11. The lanes alternate on every sample, so a
   drift in the machine touches both alike.
4. **Each timed sample is k back-to-back calls, k chosen so that k × the warm call ≥ 10 ms**
   (`SAMPLE_MIN_MS`), the way `timeit` batches a statement. k is chosen per lane from its
   fastest warm-up call — `ceil(10 ms / warm call)`, at most 200 (`CALLS_MAX`), and 1 for
   any call already at or over 10 ms. Batched calls run faster than a lone warm call (cache,
   no per-call setup), so the sample as the clock sees it usually lasts a few ms — on the
   deployed Space 3–9 ms (k × median) — which is the point: long enough that timer and
   scheduler jitter is a small share of it. The per-call time is the sample divided by k;
   every figure below is per call. *(New in v0.4 — see the change log; wording made exact in
   v0.5 after the launch review measured the samples.)*
5. **Statistics per lane, on the per-call figures:** median, P95 (nearest rank, N ≥ 20; the
   maximum for N = 11), MAD, CV (sample standard deviation over mean), min and max.
6. **The ratio** best incumbent median over algenta median, when the cell is a race; both
   absolute times are always kept and printed.
7. **Stability gate (v0.5, v0.6):** the robust spread `1.4826 × MAD / median` ≤ 15 % on every
   lane (`CV_MAX`, `ROBUST_SCALE`; `LaneResult.spread`) and the mean within 15 % of the median
   (`LaneResult.skew` — a 50/50 alternation of two timings has MAD 0 but a median that is not the
   cost; the CV would have caught it, the spread alone would not). Otherwise the cell is **noisy —
   not recorded** and no timing number is printed; the card names the gate that failed (`spread
   above 15 percent on <lane>`, or `mean more than 15 percent off the median on <lane>` when the
   spread cleared the gate). The 1-minute load average is read when the cell ends and
   **disclosed in the card's foot** (`host load 14.1`), never a gate: inside a Space the
   container reads the host's `/proc/loadavg`, not its own, and the spread and the mean/median
   guard measure what the load only predicts (v0.6 — see the change log).
8. **Budget:** 60 s per cell (`BUDGET_S`). Over it the cell is **not measurable here**.
9. **The machine is disclosed on every card:** the Space id and tier (`SPACE_ID`; the tier is
   the Hub's own answer for this Space, read once at boot from the Space runtime endpoint —
   `SPACE_HARDWARE` only states it for a local run), the CPU model from `/proc/cpuinfo`, the
   cgroup CPU quota as `n vCPU`, OS and architecture, the interpreter, `threads n` when a
   thread-count variable is set (`OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS`),
   the pinned library versions, and `rulebook v0.6`. Never a hardcoded tier; when the Hub does
   not answer, the foot names no tier.
10. **Kernel timings include the JSON marshalling across the C ABI**; the card says so.

## What the card prints

* the hero figure (the ratio, or the kernel-call median for a parity cell) and one log-scaled
  bar per lane labelled with its real median;
* the lane table: median, MAD, CV, P95 (or max), min – max, each with its unit through
  `cards.fmt_ms` (three significant figures in the unit that fits: `2.17 ms`, `0.122 ms`,
  `86.9 µs`);
* chips: the parity label, the seed, **`n = 21` or `n = 21 × k calls`** (`cards.n_chips`;
  per lane — `n = 21 × 16 calls · algenta-text`, `n = 21 × 1 call · nltk` — when a race's
  lanes batched differently), the stability gate (`stable · CV 4.0% ≤ 15%`), the UTC stamp;
* the hardware footer above, then `host load 14.1` — the machine's 1-minute load average when the
  cell ran (v0.6) — and the UTC stamp;
* a cell that did not clear the gate: the kernel's result and its parity chip stay (the value
  is not noisy, only its timing is), the timing rows are replaced by one quiet `not recorded`
  row with the cause (`cards.render_not_recorded_card`).

The How-measured disclosure of a tab carries the sentence `cards.HOW_TIMED`: *each timed
sample is k back-to-back calls lasting at least 10 ms (k from the warm call, at most 200),
the per-call time is the sample over k, and the card says n = 21 × k calls.*

## Change log

### v0.4 (2026-09-23) — batched samples

One change: rule 4. A timed sample is k back-to-back calls lasting at least 10 ms, the
per-call time is the sample over k; N, the interleaving, the statistics and both gates are
unchanged. The card prints `n = 21 × k calls`; a lane at 10 ms or slower has k = 1 and is
timed exactly as v0.3 timed it. 21 samples of 10 ms cost a fast lane 0.2 s.

Why. On the deployed Space (`thyn-ai/algenta-staging`, AMD EPYC 7R13, 8 vCPU, cpu-upgrade)
every timed run after boot came back *noisy — not recorded — spread above 15 percent*: the
hero z-test 10 of 10 visitor runs (0.09 ms median, 0.6 s per run), the Levenshtein S and M
race cells, while the lane was idle (queue depth 0, EWMA 0.43 s — jitter, not load). A
0.09 ms call timed one at a time is measured by the timer and the scheduler as much as by
the kernel: a 50 µs scheduling hiccup is 55 % of one sample. Batched into ≥ 10 ms samples
the same hiccup is 0.5 % of one sample, and the CV reads the kernel again.

The floor is measured, not guessed. The first draft used 2 ms (the smallest sample that
puts timer resolution and a typical wake-up below the gate). On the build Mac with two
`yes > /dev/null` busy loops beside other sessions (load 25–30 on 16 vCPU — above the
load gate, so the CV gate alone was measured with the load reading injected as 0), three
runs per cell and floor (the sweep log is attached to the PR):

| cell | one call (v0.3) | 2 ms | 5 ms | 10 ms | 20 ms |
|---|---|---|---|---|---|
| hero z-test, 0.14 ms | 1/3 recorded, CV 18 % | 2/3, CV 7.5 % (max 25 %) | 2/3, 6.6 % | **3/3, 3.8 % (max 7.7 %)**, k = 61 | 2/3, 14.9 % |
| Levenshtein S, algenta 0.85 ms | 1/3, 24 % | 1/3, 26 % | 1/3, 45 % | **3/3, 12.5 %**, k = 11 | 2/3, 12 % |
| Levenshtein M, algenta 2.5 ms | 1/3, 16 % | 1/3 (k = 1, unchanged), 23 % | 0/3 | **2/3, 13.4 %**, k = 5 | 1/3, 15 % |

The medians agree across floors within noise (hero 0.139–0.167 ms, S 0.85–1.04 ms,
M 2.31–2.73 ms — the spread of the medians is the machine's, not the protocol's). 10 ms
is the floor that records under noise; 20 ms buys nothing more (a longer sample catches
more preemptions in absolute terms) and costs wall time. A later run of the same script in
a heavier window (load 24–83 on 16 vCPU, 2.7× oversubscribed) recorded the hero 2 of 6 at
10 ms and 0 of 6 one call at a time, Levenshtein M 0 of 6 either way: past the load gate no
sample length reads the kernel, and that gate — not this rule — is the answer there.

What it does not change. The medians are per call and agree with the one-call medians within
noise (`tests/spaces/test_shared_bench.py::test_batching_removes_timer_jitter…` shows the
mechanism on scripted timings; the local measurement is recorded below). The ratio is the
same ratio. A cell over the load gate is still not recorded: batching answers jitter on an
idle host, not an oversubscribed one.

Local measurement: the table above (build Mac, 16 vCPU, two `yes > /dev/null` busy loops
beside the harness, other sessions running — load average above the load gate throughout,
so the CV gate alone was measured with the load reading injected as 0). The deployed host
(8 vCPU, idle lane, jitter not load) is the regime this change targets; its verification is
the post-deploy verifier's `hero_result` and `race_cell` checks recording.

### v0.3 (2026-09-22)

Two discarded warm-ups; N = 21 / 11 interleaved repeats; the 60 s budget; median, P95, MAD,
CV, min and max per lane; the ratio with both absolute times; the stability gate (CV ≤ 15 %,
load ≤ 1.5 × quota); the hardware disclosure from `/proc/cpuinfo`, the cgroup quota and
`SPACE_HARDWARE`.

## v0.5 — the gate reads the robust spread (2026-09-23, measured on the deployed Space)

Under v0.4 the deployed flagship (`thyn-ai/algenta-staging`, cpu-upgrade, AMD EPYC 8 vCPU, idle lane)
still refused most visitor presses of the hero: isolated presses 20 s apart recorded 1 of 4, then
2 of 3. The recorded cards showed why — `n = 21 × 62 calls · P95 85.6 µs · MAD 0.706 µs · spread 13 %`
and `n = 21 × 66 calls · P95 91.6 µs · MAD 1.16 µs · spread 13 %`: the classical CV (sample standard
deviation over mean) sat at 13–15 % while the MAD of the same 21 per-call samples was 0.7–1.2 µs on
an 85 µs median — a robust spread of 1–2 %. A few scheduler spikes on a shared host inflate the
standard deviation; the median and the MAD do not move. The gate therefore reads the robust spread
(`1.4826 × MAD / median`, the MAD scaled to a standard deviation for a normal sample), the same 15 %
bar, on both lanes, plus one guard the CV used to give for free: the mean must stay within 15 % of
the median (a coarse clock alternating two readings one call at a time has MAD 0 and a wrong
median; batching already evens that out, the guard names it). The classical CV stays on every card
and in the lane table; the chip reads `stable · spread 1.4% ≤ 15%`; the How-measured sentence
names both statistics.

## v0.6 — the load average is disclosed, not gated (2026-09-23, measured on the deployed Space)

v0.5 kept one rule from v0.3 beside the spread: a 1-minute load average above 1.5 × the CPU quota
refused the recording (`load 13.7 on 8 vCPU`). On the deployed flagship (`thyn-ai/algenta-staging`,
cpu-upgrade, AMD EPYC 7R13, 8 vCPU) that rule refused stable measurements: with the container's own
lane idle (one native call at a time, nothing else running) `os.getloadavg()` read 13.7–14.1 — the
*host's* load average, which is what `/proc/loadavg` shows inside a container — so four isolated
presses 15 s after a browser audit, then three of four presses and seven of seven races on a fresh
boot, came back `noisy — not recorded — load 14.1 on 8 vCPU`; the one press the load let through
recorded with its spread inside the gate. A load figure measured over a machine the container does
not own cannot gate a measurement the spread already judges directly: v0.6 reads the load average at
the end of the cell and prints it in the card's foot (`… · host load 14.1 · 2026-09-23 12:13 UTC`),
so a reader sees the machine's state beside the number, and the gate is the spread and the
mean/median guard alone. A future rule may read the container's own CPU pressure
(`/sys/fs/cgroup/cpu.pressure`) once the deployed Space has shown it; a rule that is not measured
is not a rule.

## Round 7 autopsy — where a kernel call's time goes (2026-09-23)

Measured on the build Mac (M4, `torch25-cpu-aarch64-darwin`, the published v1 packages, medians
of 9–300 calls; the shared EPYC host reads 2–4× slower):

| cell | total | to_plain | normalize | Mojo (parse + dispatch + serialize) | json in/out | decode | incumbent |
|---|---|---|---|---|---|---|---|
| haversine, one pair | 20 µs | 1 | 1 | 13 | 3 | 0 | geopy 8 µs |
| is_prime, one number | 15 µs | 0 | 1 | 12 | 2 | 0 | sympy 3–5 µs |
| word bigrams, 20,000 tokens | 19.0 ms | 2.6 | 2.8 | 7.2 | 1.2 | 4.9 | nltk 2.3 ms |
| Dijkstra, 2,000 · 8,000 | 58.6 ms | 5.8 | 11.7 | 25.6 | 4.2 | 0.6 | networkx 8.9 ms |
| Greeks, 1,000 options | 8.1 ms | 0.9 | 1.2 | 3.6 | 1.5 | 1.5 | py_vollib 17.9 ms (host) |
| betweenness, 200 · 800 | 11.4 ms | 0.5 | 0.8 | 10.6 | 0.2 | 0.1 | networkx 31.7 ms |
| Levenshtein, 600 × 600 | 2.7 ms | 0 | 0 | 2.6 | 0 | 0 | nltk 134 ms |

Three consequences, all applied the same day:

1. **A race is offered only where the kernel's compute dominates the call** (rule 6's "toy shapes
   where transport dominates", now measured). A scalar call sits on the C ABI's 12–13 µs floor
   (70–90 µs on the host) that inlined Python beats; a text or edge list moves more JSON than it
   computes. Haversine, Miller-Rabin, Dijkstra and word bigrams left the roster and stay Playground
   parity references; closeness centrality (3–7×, `scaled_values` == networkx to 1e-16) and the
   prime sieve (78,498 primes below 10^6 in 25 ms vs 329 ms) joined it; the Greeks cells grew to
   1,000 · 5,000 · 20,000 options.
2. **The Space's own overhead inside the timed lane is gone**: `hubkernel.execute` deep-copied the
   argument list and the function spec on every call — 20 µs on a scalar, 5–20 ms on a large list —
   both removed (the spec is looked up, the call keeps a shallow copy).
3. **Qualification tolerates a noisy press**: a cell qualifies on three recorded wins within five
   presses (`apps/spaces/tools/requalify.py`); a noisy press is not a run, a recorded loss still
   disqualifies (a 21.6× Levenshtein win had read "not qualified" after one noisy run of three).

Left for the next two tracks, with their measured shares: the published glue's per-element Python
passes (`to_plain`, `normalize_arguments`, `decode_value` — a quarter to a third of a batch call;
a C-level fast path in the package templates, then a republish), and the Mojo side's 20–40 MB/s
JSON (the ABI adapter's depth scan, three key lookups and the count-relation check run before the
frozen dispatch parses the request again — a single-pass adapter is additive to the frozen engine).
