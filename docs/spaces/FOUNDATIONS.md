# Spaces foundations — Hub kernels and the native lane

Internal notes for `apps/spaces/_shared/algenta_spaces/hubkernel.py` and `lane.py`
(M2). Module docstrings are the reference; this page is the runbook view: what a
Space does at boot, what every error code means, and how the §9 proof is run.

## Hub kernels inside a Space (`hubkernel.py`)

```python
from algenta_spaces import hubkernel, lane

boot = hubkernel.preload(["stats", "text", "graph"], progress=registry_hook)   # before launch()
stats = boot.loaded["algenta-stats"]          # LoadedKernel: variant, capped sha, warmup_ms
form = hubkernel.describe(stats)              # modules -> functions -> params, excluded removed
call = hubkernel.execute(stats, "ab_testing", "z_test_proportions", [50, 1000, 65, 1000])
footer = hubkernel.platform_note(boot.loaded.values())
```

* `TRUST` is the twenty capped v1 repositories (`publication_state.capped_v1_shas`),
  read from `docs/hf-kernels/release/capabilities.json` when the file can be found
  (`ALGENTA_CAPABILITIES_JSON`, a copy next to the package, or the checkout) and from
  the frozen copy in the module otherwise. `tests/spaces/test_hubkernel.py` fails
  when the frozen copy drifts from the JSON. The same holds for the card examples
  (`scripts/hf_kernels/module_descriptions.json["card_examples"]`,
  `ALGENTA_MODULE_DESCRIPTIONS_JSON`); `algenta-stats`, `algenta-llm` and the
  umbrella have no example line on their cards, so `EXTRA_CARD_EXAMPLES` supplies
  the flagship hero call, the CPU RMSNorm call and the stats call respectively.
* A card example given as text (`ab_testing.z_test_proportions(50, 1000, 65, 1000)`)
  is parsed with `ast` and `ast.literal_eval`; nothing from a file is ever evaluated.
* `warm_up` is the first native call: it pays the runtime initialisation (about a
  second cold; 66 ms measured warm-cache on an M-series Mac) so the first visitor
  does not.
* `host_floor_ok()` is the published CPU floor: `avx2` (x86-64-v3) in `/proc/cpuinfo`
  and glibc 2.35 on Linux x86_64; glibc alone on Linux aarch64; bypassed with a
  reason on macOS, where the kernel loader enforces the macOS 15 floor from each
  variant manifest. A Space below the floor holds its native tabs with the reason.

### Error codes (`HubKernelError.code`)

| code | raised by | meaning |
|---|---|---|
| `kernels_not_installed` / `torch_not_installed` | `load` | the import failed; `pip install kernels torch` |
| `unknown_family` | `load`, `repo_id_of` | not one of the twenty repositories in `TRUST` |
| `variant_unavailable` | `load` | no build for this platform (`kernels` found no variant) |
| `cache_missing` | `load` | offline and the family is not in the baked cache |
| `hub_unreachable` | `load` | network or Hub error |
| `trust_required` | `load` | `trust_remote_code` did not name a repository in the tree |
| `native_unavailable`, `platform_unsupported`, `abi_mismatch`, `init_failed`, `gpu_*` | `load` | the kernel's own loader refused; code passed through |
| `variant_unknown` | `load` | `kernel.__file__` holds no `/build/<variant>/` |
| `no_contract` | `describe`, `execute` | the module exposes neither `CONTRACT` nor `families` |
| `unknown_module`, `unknown_function`, `excluded_function` | `execute`, `function_spec` | refused before the kernel is called |
| `invalid_arguments`, `function_not_registered`, … | `execute` | the kernel's own code, passed through as `HubKernelCallError` |
| `call_failed` | `execute` | an exception without a code inside the call |
| `no_card_example`, `bad_card_example` | `card_example`, `parse_example` | no or malformed warm-up call |
| `capabilities_invalid`, `descriptions_invalid` | the loaders | a present but malformed JSON (a deploy bug, never papered over) |

## The one native lane (`lane.py`)

ABI §9: the compiled library holds one device-wide worker slot (blocking `flock`
on `/dev/null`). Two native calls issued at once do not run in parallel; the
second waits inside the library, and a timing taken from that thread reads the
queue as work. So:

* Gradio serialises at the HTTP layer with `gradio_hooks()`:
  `concurrency_id="native", concurrency_limit=1` on every native event and
  `blocks.queue(default_concurrency_limit=1, max_size=8)`.
* `Lane` serialises inside the process (Hub kernels, `algenta-runtime-native`, the
  arena subprocess). `submit` returns a `Ticket` with its position and an ETA of
  `position × EWMA(recent durations)` for the queue chip.
* Budgets bound the wait, not the call — a native call cannot be interrupted from
  Python. Past `submit + ETA + budget` a ticket raises `LaneTimeout`
  (`lane_timeout`, the code the unavailable card prints); a queued ticket is
  cancelled outright; a running one keeps running and the lane refuses new work
  with `LaneBusy` (`lane_busy`) until it returns. `lane_full` bounds the depth.

## The §9 proof, as the live test runs it

`tests/spaces/integration/test_hubkernel_live.py` (`ALGENTA_SPACES_LIVE=1`,
`-m slow`) measures **wall time against the serialised sum of warm single calls** —
the red-team gate's metric (`scripts/hf_kernels/community_cap_redteam.py`), the
only one a blocking lock cannot fool. Two checks:

1. through the lane, two `distribution_fit.fit_normal` calls over 400k floats:
   the second starts after the first ends and wall ≥ 0.8 × sum;
2. against the compiled cap, two plain threads on two library instances
   (`bayesian.bayesian_ab_test` with 1.5 M samples on `algenta-stats`,
   `text.fuzzy.levenshtein_distance` over 6,000 × 7,000 characters on
   `algenta-text`): wall ≥ 0.8 × sum, effective workers ≤ 1.25.

The second check uses scalar-argument calls on purpose: a 400k-element list spends
a visible share of its time in JSON marshalling on the Python side, which the cap
does not (and should not) serialise, so a list-heavy pair can read as 1.2
"workers" while the native executions were strictly serial.

Measured on this Mac (M-series, other work running): lane pair ratio ≈ 1.0;
cross-family pair 0.89–0.96 effective workers over three trials.

### Parity note for the hero card

`ab_testing.z_test_proportions(50, 1000, 65, 1000)` against
`statsmodels.stats.proportion.proportions_ztest`: the z statistic agrees to under
1e-12, the p-value to 8.6e-9 (the kernel's normal CDF). A card may say "matches
statsmodels to 1e-9 (z) and 1e-7 (p)"; not "1e-12" for the p-value.

## The Playground layer (`playground.py`)

Internal notes for `apps/spaces/_shared/algenta_spaces/playground.py`, the
contract-driven "run any function" layer behind the flagship's Playground tab. The
module docstring is the reference; this is the runbook view.

```python
from algenta_spaces import hubkernel, playground

loaded = hubkernel.load("stats")                                   # or the raw get_kernel() module
form = playground.form_spec(loaded, "ab_testing", "z_test_proportions")   # Form of FieldSpec
args = playground.parse_inputs(form, {"successes_a": "200", "n_a": 1000, ...})   # or ValidationError
call = playground.run(loaded, "ab_testing", "z_test_proportions", raw)   # validated, timed
text = playground.snippet("stats", "ab_testing", "z_test_proportions",
                          playground.named_args(form, call.args), mode="kernels")   # kernels|sdk|mcp
```

* **Controls from the contract.** `FieldSpec.kind`: `Int`/`UInt*` -> `int`
  (`gr.Number(precision=0)`), `Float*` -> `float`, `Bool` -> `bool`, `String` -> `str`,
  lists and structs -> `json` (`gr.Code(language="json")`, `list_of` names the element
  type). A kernel default is `required=False` with `default=None`: the value lives in
  the kernel and is filled only from the right. Excluded functions
  (`capabilities.json` + the kernel's own `excluded_functions`) are refused by
  `form_spec`, so no control is ever built for them.
* **Validation = the wrapper's rules, before the ABI.** `parse_inputs` is a port of
  the kernel's `_transport.normalize_arguments` and count guard: bools are not ints,
  64-bit int and `UInt*` ranges, finite floats, UTF-8 strings, list element types,
  exact struct keys (returned in the kernel's field order), count relations
  (`n_rows=2, n_cols=4 counts more elements than x holds (7)`), plus the plan's
  200k-element list budget. Every refusal is `ValidationError(field, reason)`; the
  packed `@u8:` buffer form the wrapper accepts is not offered to visitors.
* **Status by name, never by zero.** Engine modules report an integer `status`;
  `ok` is 380 for `normk`, 360 for `attnk`, 560 for `llmk`. Cards call
  `status_name(kernel, module, code)` and `is_ok_status(name)`.
* **Snippets are the truth.** `kernels`: `# pip install kernels torch`, the full
  twenty-repo `TRUST` list (HF-TRUST-002), `get_kernel(repo, version=1, backend="cpu",
  trust_remote_code=TRUST)`, then `k.<module>.<function>(<visitor's args>)`; `sdk`:
  `from algenta import libraries` and `libs.module("<module>").<function>(...)`; `mcp`:
  the JSON-RPC 2.0 `tools/call` frame for `execute_runtime_library`. Long calls wrap one
  argument per line; every Python snippet compiles, every JSON parses (tests exec them
  against fakes).
* **Hero table.** `hero_functions()` is the plan's fifteen entries as data; three are
  recorded where the published contracts actually ship them: the ML metric is
  `calibration.calibration_curve` (`ml_metrics_extended` has only per-term scalars), the
  n-gram tokenizer `text.tokenizer` lives in `algenta-llm`, dHash `perceptual_hash` in
  `algenta-crypto`, and the sampling entry is `llmk.generate.greedy_argmax_flat`. With a
  `{family: kernel}` mapping the table is validated against the loaded contracts
  (`HeroMismatchError`). Fixtures `tests/spaces/fixtures/contract_algenta_stats.json`
  (whole family) and `hero_contracts.json` (hero modules of the other nine) are the
  darwin contracts, sha-stamped; the live test fails when they drift.

Measured on this Mac (`tests/spaces/integration/test_playground_live.py`, nine
families, `torch25-cpu-aarch64-darwin`): every hero runs from its default arguments;
warm calls 0.3–1.2 ms (RMSNorm 5 ms), the **first call of a family 76–112 ms** — the
lazy native initialisation `hubkernel.warm_up` pays at boot; 1,419 callable functions
all produce a form; two threads over a 60 ms Levenshtein call: wall 0.44 s against a
serialised sum of 0.36 s, 0.83 effective workers (§9 holds).
