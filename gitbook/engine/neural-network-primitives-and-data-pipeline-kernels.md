---
icon: puzzle-piece
description: Eleven unrelated small libraries closing out the kernel-documentation backlog -- scalar activation functions, cellular automata, a string-similarity column-name ranker, two distinct data-pipeline utilities, streaming groupby aggregation, NumPy-equivalent math, GPU performance-modeling formulas, single-step graph algorithms, a minimal discrete-event simulator, and digital audio signal processing.
---

# Neural network primitives and data-pipeline kernels

Eleven modules with no shared subject, grouped onto one page only because each is small enough
that a page of its own would be mostly frontmatter. Read individually, this is: ten scalar
activation functions from the transformer era (`activations`), 2D and 1D cellular automata
(`cellular`), a string-edit-distance column-name ranker for a data-source planner (`column_rank`),
training-data curation formulas (`data_pipeline`) alongside a completely unrelated set of generic
map/filter/reduce primitives that happens to share half a name (`pipeline`), streaming Welford
groupby aggregation (`pandas_groupby`), numerically-stable NumPy-equivalent ufuncs (`numpy_ops`),
closed-form GPU performance-modeling formulas (`gpu_kernels`), single-step graph-traversal and
centrality formulas (`graph_algorithms`), a from-scratch discrete-event simulator with an M/M/1
queue on top (`simulation`), and digital audio signal-processing primitives (`audio`). Several of
these names collide, in spirit or literally, with modules this corpus has already documented under
a different page — each collision is checked against the real source below rather than assumed.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

runtime.execute("activations", "swish", [2.0])["result"]
# 1.7615941559557646 -- Swish/SiLU: x * sigmoid(x)

runtime.execute("audio", "midi_to_frequency", [60.0])["result"]
# 261.6255653005986 -- MIDI note 60 is middle C
```

## The modules

| Module | What it does |
| --- | --- |
| `activations` | Ten scalar neural-network activation functions from the transformer era: GELU (three near-identical spellings), Swish/SiLU, SwiGLU, Mish, ELU, SELU, Hard-Swish, and ReLU6 |
| `cellular` | 2D and 1D cellular automata: Conway's Game of Life (step, neighbor counting, still-life detection, population history) and Wolfram elementary CA (rule lookup, single-step, multi-step run), plus grid utilities |
| `column_rank` | A single JSON-in/JSON-out entry point, `run_column_rank`, that ranks candidate column names against a hint by edit-distance and bigram-overlap string similarity |
| `data_pipeline` | Training-data curation formulas: sequence-packing efficiency, MinHash dedup band matching, curriculum difficulty, DoReMi-style dataset mixing weight, token accounting, quality filtering, shard balance, streaming-buffer fullness, epoch sample shuffling, and augmentation loss weight |
| `pipeline` | Twelve generic, domain-free data-processing primitives: map, filter, the four reductions, chained map-then-filter, fixed-size batching, flattening, zipping, sliding windows, and order-preserving uniqueness |
| `pandas_groupby` | Streaming groupby aggregation via Welford's online algorithm: running mean, variance, min, max, sum, count, standard deviation from the variance accumulator, weighted mean, an approximate running median, and a skewness term |
| `numpy_ops` | Ten NumPy-equivalent element-wise ufuncs, several with an explicit numerically-stable branch: clip, log1p, expm1, sign, Heaviside step, normalized sinc, log-sum-exp, hypot, linear interpolation, and bin membership |
| `gpu_kernels` | Closed-form GPU performance-modeling formulas: shared-memory tile sizing, warp occupancy, roofline arithmetic intensity and achievable throughput, memory-coalescing efficiency, kernel-launch overhead ratio, a tensor-core FLOPs estimate, flash-attention HBM read volume, register pressure, and SM utilization |
| `graph_algorithms` | Ten single-step graph formulas: Dijkstra and Bellman-Ford edge relaxation, one PageRank contribution, normalized betweenness, local clustering coefficient, degree and closeness centrality, an eigenvector-centrality power-iteration step, Newman-Girvan modularity contribution, and graph density |
| `simulation` | A from-scratch discrete-event engine (`SimState`/`Event` structs, event scheduling, popping, cancellation, run-until) built on a linear-scan sorted insert, plus a fixed-seed M/M/1 queue simulator |
| `audio` | Digital audio signal-processing primitives operating on `List[Float64]` sample buffers: amplitude/dB conversion, MIDI/frequency mapping, sine generation, RMS amplitude, zero-crossing rate, running-max envelope, peak normalization, and weighted signal mixing |

## `activations`: the transformer-era activations, distinct from `nn_layers`'s classic four

[Transformer blocks and normalization reference kernels](transformer-blocks-and-normalization-reference-kernels.md)
already documents `nn_layers`, which has its own "four activations" (`relu`, `sigmoid_activation`,
`tanh_activation`, `softmax_layer`, plus `leaky_relu` alongside them) — but every one of those
operates on a `List[Float64]` vector and covers the pre-2015 activation vocabulary. `activations`
(this page) is the complementary, non-overlapping half: ten **scalar** `Float64`-valued formulas
(most take one `x`; `elu` and `swiglu` take a second scalar parameter) from the Swish/GELU/Mish
generation of activations that made transformer feed-forward layers work, and there is zero name
overlap between the two modules' function lists.

| Function | Formula |
| --- | --- |
| `gelu(x)` | `x * 0.5 * (1 + tanh(0.7978845608*(x + 0.044715*x^3)))` — despite its own docstring's "(exact)" label, this is the tanh approximation, not `x * Phi(x)` |
| `gelu_fast(x)` | The same tanh approximation as `gelu`, with the constant to full double precision (`0.7978845608028654`) |
| `gelu_new(x)` | The same formula again, restructured as `x*(1+0.044715*x^2)` instead of `x+0.044715*x^3` — the GPT-2/BERT spelling |
| `swish(x)` | `x / (1 + exp(-x))` — SiLU |
| `swiglu(x, gate)` | `swish(gate) * x` (Shazeer 2020) |
| `mish(x)` | `x * tanh(log(1+exp(x)))` |
| `elu(x, alpha)` | `x` if `x >= 0`, else `alpha*(exp(x)-1)` |
| `selu(x)` | `elu` scaled by `lambda=1.0507009873554805` with fixed `alpha=1.6732632423543772` |
| `hard_swish(x)` | `x * clip(x+3, 0, 6) / 6` — the MobileNetV3 piecewise approximation |
| `relu6(x)` | `clip(x, 0, 6)` |

`gelu`, `gelu_fast`, and `gelu_new` are, in practice, the same function three times. Reading all
three bodies side by side: they compute the identical tanh-based approximation, differing only in
how many digits of the `0.7978845608...` constant are written out and in which order the
multiplication is associated. Hand-computed at `x = 1.0` (verified independently against the
published formulas): `gelu(1.0) = 0.841191990607477`, `gelu_new(1.0) = 0.8411919906082768` — the
two agree to 12 significant figures, and the residual is floating-point association noise, not a
different activation. [MLP block kernels](mlp-block-kernels.md) already flags the more important
fact this implies: **none of the three is the erf-based "exact" GELU** its own name and docstring
suggest. Measured against `x * 0.5 * (1 + erf(x/sqrt(2)))`, the gap between the tanh family here
and the true erf form grows to `4.73e-4` at `x = 2.7` — small enough to look like rounding, large
enough that Hugging Face's `hidden_act` config treats `"gelu"` (erf) and `"gelu_new"` /
`"gelu_pytorch_tanh"` (tanh) as genuinely different activations. `mlpk.activation.mlp_gelu_erf`,
documented on that page, is what actually supplies the erf form; nothing in `activations` does.

`swiglu(3.0, 2.0)` computes `swish(2.0) * 3.0 = 1.7615941559557646 * 3.0 = 5.284782467867294` — the
identical formula (`SiLU(gate) * x`) that
[Transformer blocks and normalization reference kernels](transformer-blocks-and-normalization-reference-kernels.md)'s
own `transformer_blocks.gated_feedforward(3.0, 2.0)` example computes independently, agreeing to
the same handful of low bits both float implementations share. Two different modules in this
codebase implement the same gated-activation formula and land on the same number.

No `tests/mojo/test_wave*.mojo` file exercises `activations` with pinned expected values; the only
test file is `test_activations.mojo`, an auto-generated finiteness smoke check. Every number in
this section was computed independently in Python from `mojo/engine/activations.mojo`'s published
bodies and is reproducible by re-running the same arithmetic.

## `cellular`: Game of Life and elementary CA — a distinct module from `cellular_automata`

The runtime also ships a same-subject, differently-scoped module named `cellular_automata`
(`mojo/engine/cellular_automata.mojo`), already documented at
[Dimensionality, information theory, and complex systems kernels](dimensionality-information-theory-and-complex-systems-kernels.md).
The two are not the same code under two names. `cellular_automata`'s functions operate on a single
cell at a time — `game_of_life_cell(is_alive, live_neighbors)` takes a neighbor **count** already
computed by the caller and returns the next state of one cell, and it additionally covers Langton's
Ant, Wireworld, Rule 110, and majority/parity voting, none of which `cellular` has. `cellular` (this
page) operates on the **whole grid or lattice** at once: `game_of_life_step(grid, rows, cols)` takes
a full `List[List[Int]]` and returns the next full grid, doing its own neighbor counting internally
via `count_neighbors`; `run_elementary_ca` returns the entire history of a 1D CA as a
`List[List[Int]]` rather than one step. Neither module imports the other, and the runtime's test
generator treats them as two independent namespaces.

`tests/mojo/test_wave50.mojo` pins real numeric behavior for this module (its docstring literally
announces "200 LIBRARY MILESTONE"). Rule 30 from a single live cell in a 7-wide lattice:

```python
state = [0, 0, 0, 1, 0, 0, 0]
runtime.execute("cellular", "elementary_ca_step", [state, 30])["result"]
# [0, 0, 1, 1, 1, 0, 0]
```

Rule 30's neighborhood table (`rule_lookup(left, center, right, 30)`) maps `(1,1,0) -> 0` and
`(0,0,1) -> 1`, and stepping the single-center-cell start through it produces exactly the
three-cell-wide pattern above — the canonical first step of Wolfram's Rule 30, matched bit for bit
against the pinned test. A 2x2 block placed inside a 4x4 grid is Conway's classic still life:

```python
grid = [[0,0,0,0],[0,1,1,0],[0,1,1,0],[0,0,0,0]]
runtime.execute("cellular", "is_still_life", [grid, 4, 4])["result"]
# True -- every cell in the block has exactly 3 neighbors (itself's 2x2 partners plus corners),
# so game_of_life_step leaves it unchanged
runtime.execute("cellular", "population_history", [grid, 4, 4, 5])["result"]
# [4, 4, 4, 4, 4, 4] -- population constant across 5 generations, steps+1 entries
```

## `column_rank`: string similarity, not statistics — and a request field with no effect

The hint that motivated this page's scope guessed "column-rank statistics." Reading
`column_rank.mojo`'s own docstring ("lightweight resident ranking support for the planner") and its
one contract-exposed function corrects that: `run_column_rank` has nothing to do with rank
statistics. It is a fuzzy string-matching ranker that scores candidate column names against a text
hint, for a data-source schema-mapping planner. The formula, read directly from `_candidate_score`:

```
name_sim = max(edit_similarity(hint_norm, candidate_norm), dice_coefficient(hint_norm, candidate_norm))
score    = clip(0.78 * name_sim + type_boost + token_overlap_boost, 0, 1)
```

where `edit_similarity` is `1 - levenshtein(a,b)/max(len(a),len(b))` and `dice_coefficient` is the
Sorensen-Dice coefficient over character bigrams (both from `string_distance.mojo`); `_normalize`
lowercases, keeps only alphanumerics, and collapses any run of non-alphanumeric characters
(underscores, spaces, punctuation) into a single space, so `"unit_price"` and `"unit price"`
normalize to the identical string `"unit price"`.

**`run_column_rank` reads a `context` field out of its own request payload and then never uses
it.** The source assigns `var context = payload.get("context", ...)` and the variable is never
referenced again; `query_source_id` and `query_role_id` are hardcoded `0` two lines later, and
those hardcoded zeros are what get passed into `_role_boost`/`_source_boost` for every candidate —
both of which return `0.0` whenever either id is `<= 0`. So `type_boost` is exactly `0.0` on every
call through this entry point, regardless of what a caller puts in `context`. (The struct behind
this module, `ResidentColumnRankState`, has a separate `run_query`/`run_batch` path that *does*
read `source_id`/`role_id` out of each query — but only `run_column_rank` is declared in the
runtime contract, so that path is not reachable through `runtime.execute`.) Relatedly, the JSON
this function returns always contains the literal `"ambiguous":false` — the confidence gap between
the top two candidates is computed and returned in the `gap` field, but nothing in this code path
ever turns that gap into the `ambiguous` flag its own output schema carries.

A worked example, hand-computed from the real formula and checked against the schema
`test_column_rank.mojo`'s own smoke test exercises (`{"hint":"unit price","candidates":[...]}`):

```python
import json

payload = {
    "hint": "unit price",
    "candidates": [
        {"source": "orders", "column": "unit_price"},
        {"source": "orders", "column": "unit_cost"},
    ],
    "top_k": 5,
}
raw = runtime.execute("column_rank", "run_column_rank", [json.dumps(payload)])["result"]
json.loads(raw)
# {"ranked": [
#    {"column": "unit_price", "score": 0.86, "name_sim": 1.0,  "type_boost": 0.0, ...},
#    {"column": "unit_cost",  "score": 0.43, "name_sim": 0.5,  "type_boost": 0.0, ...}
#  ], "ambiguous": false, "gap": 0.43}
```

`"unit_price"` normalizes to the same string as the hint, so `name_sim = 1.0` exactly — but the
score still comes out `0.86`, not `1.0`: `0.78 * 1.0 = 0.78`, plus `token_overlap_boost = 0.08`
(both hint tokens, `"unit"` and `"price"`, are found inside the candidate), for `0.86`. `type_boost`
contributes nothing, for the reason above. `"unit_cost"` has a Levenshtein distance of 5 against a
max length of 10 (`edit_similarity = 0.5`, and the bigram Dice score is lower at `0.4706`, so
`edit_similarity` wins the `max`), plus a partial token match (`"unit"` found, `"price"` not) worth
`0.04`, for `0.78*0.5 + 0.04 = 0.43`.

This is the third distinct implementation of "rank columns by name" in the runtime, not a
duplicate of the other two. [Vector-based ranking kernels](vector-ranking-kernels.md) documents
`vector_kernels.ranker.run_column_rank_v2` (cosine similarity over a 64-bucket Float32 SIMD bigram
vector plus token-Jaccard) and names `engines.column_ranker` as its own non-SIMD predecessor (also
cosine-over-bigrams). `column_rank` (this page) shares no code with either: it uses Levenshtein
edit distance and Dice-on-bigrams instead of cosine similarity, integer `role_id`/`source_id` fields
instead of string role/source values, and — per the finding above — never actually applies its type
boost through this call path, where `run_column_rank_v2` does compute and apply its own analogous
boosts.

## `data_pipeline` and `pipeline`: two modules, one shared word, no shared code

These names differ by one word and nothing else links them. `data_pipeline.mojo`'s docstring is
"Training data pipeline: packing, dedup, curriculum, mixing" — ten formulas specific to curating an
LLM pretraining corpus, each taking domain-specific scalars (perplexity, token counts, MinHash
signatures). `pipeline.mojo`'s docstring is "Data Pipeline / Workflow utilities... map, filter,
reduce, batch, window, flatten, and zip primitives," explicitly replacing "luigi/prefect core
data-pipeline patterns" — twelve generic functions over a bare `List[Float64]`, with no concept of
a token, a document, or a training epoch. Neither module imports the other or shares a function
name. (A third, unrelated module — `pipelines.mojo`, plural, an sklearn-`Pipeline`-style
fit/transform composer over `StandardScaler`/`MinMaxScaler`/`log1p`/clip/median-impute steps — is
already documented at [ML pipelines](ml-pipelines.md) and is a fourth, distinct thing again.)

`data_pipeline`, hand-verified:

```python
runtime.execute("data_pipeline", "sequence_packing_efficiency", [950.0, 1024.0])["result"]
# 0.927734375 -- 950 real tokens out of 1024 padded slots

runtime.execute("data_pipeline", "dataset_mixing_weight", [2.0, 1.5, 0.5])["result"]
# 2.718281828459045 -- exp((2.0-1.5)/0.5) = exp(1.0), unnormalized DoReMi-style domain weight

runtime.execute("data_pipeline", "quality_filter_score", [30.0, 50.0, 0.1, 0.9])["result"]
# 0.7 -- 0.4*(1-30/50) + 0.3*(1-0.1) + 0.3*0.9 = 0.16 + 0.27 + 0.27
```

`pipeline`'s twelve functions are pinned end to end in `tests/mojo/test_wave26.mojo` (not an
auto-generated smoke test):

```python
runtime.execute("pipeline", "chain_map_filter", [[1.0,2.0,3.0,4.0,5.0], 0, 0, 5.0])["result"]
# [9.0, 16.0, 25.0] -- square each (map_op=0), keep > 5.0 (filter_op=0): 1,4,9,16,25 -> 9,16,25

runtime.execute("pipeline", "batch", [[1.0,2.0,3.0,4.0,5.0], 2])["result"]
# [[1.0, 2.0], [3.0, 4.0], [5.0]] -- 3 batches, the last one short

runtime.execute("pipeline", "unique_values", [[1.0,2.0,2.0,3.0,1.0]])["result"]
# [1.0, 2.0, 3.0] -- first-occurrence order, duplicates dropped
```

## `pandas_groupby`: Welford's algorithm, the accumulator [Windowed aggregates](streaming-windows.md) wraps

All ten functions are individual update steps of streaming (single-pass) aggregation — none of
them holds state itself; the caller threads the running accumulator through repeated calls. Running
the classic worked example for Welford's algorithm (`[2, 4, 4, 4, 5, 5, 7, 9]`, a textbook data set
chosen because its population variance is a clean `4.0`) through `group_mean_update` and
`group_variance_update` one observation at a time converges to `mean = 5.0`, `M2 = 32.0` after all
eight points:

```python
runtime.execute("pandas_groupby", "group_std_from_variance", [32.0, 8.0, 0.0])["result"]
# 2.0  -- population std: sqrt(32/8)
runtime.execute("pandas_groupby", "group_std_from_variance", [32.0, 8.0, 1.0])["result"]
# 2.138089935299395 -- sample std: sqrt(32/7), ddof=1
```

`group_median_approx` is explicitly named as a simplified P²-style approximation, not an exact
running median: each new observation nudges the estimate by a fixed step of `1/(n+1)` in the
direction of the new value, so the estimate nudges but never jumps, and it converges only
gradually toward the true median as more points arrive. `pandas_groupby`'s mean/variance
accumulators are not only used standalone — 
[Streaming, structured output, and time kernels](streaming-structured-output-and-time-kernels.md)
names this exact module as one of the frozen kernels its own `streaming.windows` rolling
aggregates are built by wrapping, alongside `timeseries_stats.rolling_mean` and
`online_learning`'s exponential updates.

## `numpy_ops`: ufuncs with a real numerical-stability branch, verified against Python's own

Every `np_log1p`/`np_expm1` call under `|x| < 1e-4` takes a Taylor-series branch instead of calling
`log`/`exp` directly, specifically to avoid catastrophic cancellation for `x` near zero (`log(1+x)`
computed directly loses precision because `1+x` rounds close to `1.0` before the subtraction that
matters ever happens). Checked against Python's own `math.log1p`/`math.expm1` (which use the same
technique): `np_log1p(1e-5)` computes `9.999950000333334e-06` against Python's
`9.999950000333332e-06` — agreement to 14 significant figures, the two implementations of the same
numerical trick landing on the same answer.

```python
runtime.execute("numpy_ops", "np_logaddexp", [0.0, 0.0])["result"]
# 0.6931471805599453 -- log(exp(0)+exp(0)) = log(2), computed via the max-subtraction trick

runtime.execute("numpy_ops", "np_sinc", [1.0])["result"]
# 3.8981718325193755e-17 -- sin(pi)/pi is not exactly zero in floating point; sinc(0) is the
# one hardcoded exception (returns 1.0) precisely because the formula's own 0/0 would not resolve

runtime.execute("numpy_ops", "np_digitize_bin", [3.0, 2.0, 3.0])["result"]
# 0.0 -- the right edge is exclusive: x==3.0 falls OUTSIDE [2.0, 3.0)
```

## `gpu_kernels`: performance-modeling arithmetic, not the GPU dispatch layer documented elsewhere

[GPU acceleration kernels](gpu-acceleration-kernels.md) documents `accel.*` — the status vocabulary
that resolves an `auto`/`accel`/`cpu` policy to a real backend, and `accel.gemm_metal`, an actual
kernel that runs on the Metal GPU. `gpu_kernels` (this page) dispatches nothing and touches no
hardware: every function is a closed-form estimate a developer would otherwise work out on paper —
tile sizes, occupancy fractions, roofline throughput — and none of them are reachable from, or
referenced by, `accel.*`. They are referenced elsewhere, though:
[GEMM kernels](gemm-kernels.md) uses `gpu_kernels.tile_size_for_smem` directly to recompute a real
tiling factor from an actual cache size, rather than hardcoding one.

```python
runtime.execute("gpu_kernels", "tile_size_for_smem", [49152.0, 4.0, 2.0])["result"]
# 64.0 -- 48 KiB of shared memory, FP32, 2 tile operands (A and B): sqrt(49152/8)=78.4,
# floored to 78, then rounded DOWN to the nearest power of two -- 64, not 78

runtime.execute("gpu_kernels", "roofline_performance", [2000.0, 989.0, 3.35])["result"]
# 989.0 -- compute-bound: memory_bound = 3.35 TB/s * 2000 FLOPs/byte = 6700 TFLOPS, which
# exceeds the 989 TFLOPS compute ceiling, so the ceiling wins
runtime.execute("gpu_kernels", "roofline_performance", [1.0, 989.0, 3.35])["result"]
# 3.35 -- same GPU, low arithmetic intensity: now memory-bound, and bandwidth wins instead

runtime.execute("gpu_kernels", "kernel_launch_overhead_ratio", [5.0, 7.0])["result"]
# 0.5833333333333334 -- a 5us kernel with 7us of launch overhead spends more time launching
# than computing; the same 7us overhead against a 1000us kernel is under 1%
```

{% hint style="warning" %}
**`tensor_core_flops`'s docstring and its body disagree.** The docstring states the formula as
`TFLOPS = 2MNK x clock x n_sms x ops_per_cycle / 1e12`, but there is no `ops_per_cycle` parameter
anywhere in the function's signature, and the actual body divides by `1e3`, not `1e12`:
`2.0 * m * n * k * clock_ghz * n_sms / 1e3`. Read literally, the number this function returns is
not TFLOPS in any standard unit — it is a relative sizing heuristic that scales with the matmul's
FLOP count, clock, and SM count, three real orders of magnitude away from what its own docstring
claims to compute. Treat its output as a same-GPU, same-precision comparative score across matmul
shapes, not as a calibrated hardware throughput number.
{% endhint %}

## `graph_algorithms`: single-step formulas, a bare name distinct from `graph.algorithms`

[Exact numerics and graph kernels](exact-numerics-and-graph-kernels.md) already flags this exact
collision from its own side: "the runtime also ships a bare, undotted `graph_algorithms` module...
not documented on this page, and not the same thing" — its functions "are single-step *formulas* a
traversal would call once per edge or once per iteration." Reading `graph_algorithms.mojo` directly
confirms that characterization completely: there is no graph data structure anywhere in this
module, no adjacency list, no priority queue. `dijkstra_relax` and `bellman_ford_relax` are, in
fact, the exact same three-line function (`min(dist_v, dist_u + edge_weight)`) written out twice
under two names — the difference between the two algorithms lives entirely in the caller's
iteration discipline (Dijkstra visits each node once via a priority queue; Bellman-Ford relaxes
every edge up to `n-1` times and tolerates negative weights), not in this kernel, which does not
know or care which discipline is being used.

```python
runtime.execute("graph_algorithms", "pagerank_update", [0.1, 5.0, 0.85, 100.0])["result"]
# 0.0185 -- teleport (1-0.85)/100=0.0015, plus damping*0.1/5=0.017; caller sums this per in-neighbor

runtime.execute("graph_algorithms", "betweenness_centrality_norm", [10.0, 10.0, 1.0])["result"]
# 0.1388888... -- directed: norm = (10-1)*(10-2) = 72
runtime.execute("graph_algorithms", "betweenness_centrality_norm", [10.0, 10.0, 0.0])["result"]
# 0.2777777... -- undirected halves the normalizer: 72/2=36, doubling the same raw count's score

runtime.execute("graph_algorithms", "modularity_contribution", [0.0, 3.0, 4.0, 20.0])["result"]
# -0.3 -- no edge here, but two degree-3/4 nodes were "expected" 12/(2*20)=0.3 of an edge by
# chance; the contribution goes negative exactly when a community groups nodes that are not
# actually connected
```

## `simulation`: a from-scratch discrete-event core, unrelated to `discrete_event.*`

[Discrete-event simulation & queueing](discrete-event-simulation.md) documents `discrete_event.*` —
six modules with a binary-heap calendar, named RNG streams addressed by coordinate, MSER-5
transient detection, and Student-t confidence intervals on replicated runs. `simulation` (this page)
is a much smaller, earlier design: a single `SimState` struct holding parallel `List` arrays for
pending and completed events, with `schedule_event` maintaining sort order by a **linear insertion
scan** rather than a heap, and `mm1_simulate` drawing its exponential inter-arrival and service
times from a hand-rolled linear congruential generator seeded with the **literal constant `42` on
every call** — the function's signature has no seed parameter at all, so `mm1_simulate(1.0, 1.0,
5)` returns the exact same three numbers every time it is called, with no way for a caller to ask
for a different sample path.

Because several functions here take a `mut` `SimState`, calling this module through
`runtime.execute` means reading the updated struct back out of `mutated_args` and feeding it
into the next call — the same pattern documented for `heap`/`queue_ds`/`trie` in
[Data structures and algorithms kernels](data-structures-and-algorithms-kernels.md). Verified
directly against `tests/mojo/test_wave23.mojo`'s own pinned assertions:

```python
sim = runtime.execute("simulation", "create_sim", [])["result"]
sim = runtime.execute("simulation", "schedule_event", [sim, 10.0, 1])["mutated_args"]["state"]
sim = runtime.execute("simulation", "schedule_event", [sim, 3.0, 2])["mutated_args"]["state"]
sim = runtime.execute("simulation", "schedule_event", [sim, 7.0, 3])["mutated_args"]["state"]

r = runtime.execute("simulation", "next_event", [sim])
r["result"]                              # {"time": 3.0, "event_type": 2, "entity_id": 1}
# -- earliest TIME wins regardless of insertion order: 3.0 was scheduled last, and still pops first
sim = r["mutated_args"]["state"]
```

`mm1_simulate(1.0, 1.0, 5)` — hand-run through the exact LCG in `mojo/engine/simulation.mojo`
(`seed = (1103515245*seed + 12345) & 0x7FFFFFFF`) — returns
`[0.954881518703712, 1.92577535539969, 0.7941214425046815]` (avg wait, avg system time,
utilization), every time, from every caller, because the seed is not an input.

## `audio`: signal-level DSP, distinct from both `psychoacoustics` and `acoustics`

The runtime has three modules with "sound" in scope and no overlap between any pair of them.
[Biomedical, biomechanics, and psychoacoustics kernels](biomedical-engineering-kernels.md)'s
`psychoacoustics` models how the ear and brain *perceive* a sound (loudness in phons/sones, the
Bark critical-band scale, masking). [Acoustics, optics, and radiative materials kernels](acoustics-optics-and-radiative-materials-kernels.md)'s
`acoustics` models the *physics* of sound propagation (inverse-square law, room reverberation,
Doppler shift). `audio` (this page) is the third layer beneath both: plain digital signal
processing over a `List[Float64]` sample buffer, with no ear model and no propagation physics —
amplitude ↔ decibel conversion, MIDI ↔ frequency mapping, sine generation, RMS, zero-crossing rate,
envelope, peak normalization, and weighted mixing. No function name is shared across all three
modules.

Every number below is pinned in `tests/mojo/test_wave35.mojo`, not hand-derived:

```python
runtime.execute("audio", "amplitude_to_db", [10.0])["result"]
# 20.0 -- 20*log10(10/1.0)

runtime.execute("audio", "frequency_to_midi", [440.0])["result"]
# 69.0 -- A440 is MIDI note 69 by construction
runtime.execute("audio", "midi_to_frequency", [60.0])["result"]
# 261.6255653005986 -- middle C

sine = runtime.execute("audio", "generate_sine", [1.0, 1000.0, 1000])["result"]
runtime.execute("audio", "rms_amplitude", [sine])["result"]
# ~0.7071 -- RMS of a full-amplitude sine wave is 1/sqrt(2), regardless of frequency

runtime.execute("audio", "mix_signals", [[1.0,2.0,3.0], [10.0,20.0,30.0], 0.5])["result"]
# [5.5, 11.0, 16.5] -- weight 0.5 is a plain average of the two signals
```

## Verification notes

Four modules on this page have real, hand-checked numeric test coverage beyond an auto-generated
finiteness smoke test: `cellular` and `pipeline` in `tests/mojo/test_wave50.mojo` and
`test_wave26.mojo` respectively, `simulation` in `test_wave23.mojo`, and `audio` in
`test_wave35.mojo`. The other seven — `activations`, `column_rank`, `data_pipeline`,
`pandas_groupby`, `numpy_ops`, `gpu_kernels`, and `graph_algorithms` — have only their
auto-generated `mojo/tests/libs/test_*.mojo` file, which calls each function once with a placeholder
argument and checks only that the result is finite. Every worked example above for those seven was
computed independently in Python from the real formulas in each module's `.mojo` source and is
reproducible by re-running the same arithmetic; none is lifted from a test fixture that does not
exist.

**Next:** see [MLP block kernels](mlp-block-kernels.md) for the erf-based GELU `activations` is
missing, [Discrete-event simulation & queueing](discrete-event-simulation.md) for the production
engine `simulation` is not, or the [Runtime library catalog](runtime-library-catalog.md) for every
module and function.
